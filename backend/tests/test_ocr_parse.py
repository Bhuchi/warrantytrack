"""Textract AnalyzeExpense -> the `extracted` shape in docs/api.md.

Pure parsing, so no AWS and no database. This is where OCR accuracy actually
lives: Textract returns labelled fields, but every receipt writes its date and
its total differently, and a wrong guess is worse than a blank field because
the user accepts it without looking.
"""

from __future__ import annotations

import pytest

from app.services.ocr import OcrError, parse_expense_response


def summary(field_type: str, text: str, confidence: float = 99.0) -> dict:
    return {
        "Type": {"Text": field_type},
        "ValueDetection": {"Text": text, "Confidence": confidence},
    }


def response(summary_fields: list[dict], line_items: list[list[dict]] | None = None) -> dict:
    """One ExpenseDocument, shaped the way Textract returns it."""
    return {
        "ExpenseDocuments": [
            {
                "SummaryFields": summary_fields,
                "LineItemGroups": [
                    {
                        "LineItems": [
                            {"LineItemExpenseFields": fields}
                            for fields in (line_items or [])
                        ]
                    }
                ],
            }
        ]
    }


def test_reads_a_whole_receipt() -> None:
    parsed = parse_expense_response(
        response(
            [
                summary("VENDOR_NAME", "Power Buy"),
                summary("INVOICE_RECEIPT_DATE", "01/03/2025"),
                summary("TOTAL", "฿32,900.00"),
            ],
            [
                [
                    summary("ITEM", "Dell Latitude 5540"),
                    summary("PRICE", "32,900.00"),
                    summary("PRODUCT_CODE", "ABC123"),
                ]
            ],
        )
    )

    assert parsed["vendor_name"] == "Power Buy"
    assert parsed["purchase_date"] == "2025-03-01"
    assert parsed["total_amount"] == "32900.00"
    assert parsed["currency"] == "THB"
    assert parsed["line_items"] == [
        {"name": "Dell Latitude 5540", "serial_number": "ABC123", "price": "32900.00"}
    ]


def test_multi_line_invoice_keeps_every_item() -> None:
    """One invoice, several assets — the case CLOUDAPPG5-96 exists for."""
    parsed = parse_expense_response(
        response(
            [summary("VENDOR_NAME", "JIB")],
            [
                [summary("ITEM", "Laptop A"), summary("PRICE", "30000")],
                [summary("ITEM", "Laptop B"), summary("PRICE", "31000")],
                [summary("ITEM", "Mouse"), summary("PRICE", "590")],
            ],
        )
    )
    assert [item["name"] for item in parsed["line_items"]] == [
        "Laptop A",
        "Laptop B",
        "Mouse",
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2025-03-01", "2025-03-01"),
        ("01/03/2025", "2025-03-01"),   # day first: this is a Thai project
        ("01-03-2025", "2025-03-01"),
        ("1 Mar 2025", "2025-03-01"),
        ("March 1, 2025", "2025-03-01"),
        ("  2025-03-01  ", "2025-03-01"),
        ("not a date", None),
        ("", None),
        ("13/13/2025", None),           # impossible, so no guess
        ("01/03/1900", None),           # too old to be a purchase
    ],
)
def test_date_readings(text: str, expected: str | None) -> None:
    parsed = parse_expense_response(response([summary("INVOICE_RECEIPT_DATE", text)]))
    assert parsed["purchase_date"] == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("32,900.00", "32900.00"),
        ("฿32,900.00", "32900.00"),
        ("32900", "32900.00"),
        ("THB 1,234.56", "1234.56"),
        ("$1,000", "1000.00"),
        ("1.234.567", None),            # ambiguous, so no guess
        ("-50.00", None),               # a refund line is not a price
        ("", None),
        ("abc", None),
    ],
)
def test_amount_readings(text: str, expected: str | None) -> None:
    parsed = parse_expense_response(response([summary("TOTAL", text)]))
    assert parsed["total_amount"] == expected


@pytest.mark.parametrize(
    ("total_text", "expected"),
    [("฿100.00", "THB"), ("$100.00", "USD"), ("THB 100", "THB"), ("100.00", None)],
)
def test_currency_is_sniffed_from_the_total(total_text: str, expected: str | None) -> None:
    """Textract only sometimes returns a CURRENCY field; the total carries it."""
    parsed = parse_expense_response(response([summary("TOTAL", total_text)]))
    assert parsed["currency"] == expected


def test_explicit_currency_field_wins() -> None:
    parsed = parse_expense_response(
        response([summary("CURRENCY", "USD"), summary("TOTAL", "฿100.00")])
    )
    assert parsed["currency"] == "USD"


def test_most_confident_reading_wins() -> None:
    """Textract can return the same field twice; take the one it believes."""
    parsed = parse_expense_response(
        response(
            [
                summary("VENDOR_NAME", "POWER BUY CO", confidence=40.0),
                summary("VENDOR_NAME", "Power Buy", confidence=98.0),
            ]
        )
    )
    assert parsed["vendor_name"] == "Power Buy"


def test_a_bad_photo_yields_blanks_not_an_error() -> None:
    """Every field is optional: the review screen is built to be filled in."""
    parsed = parse_expense_response(response([]))
    assert parsed == {
        "vendor_name": None,
        "purchase_date": None,
        "total_amount": None,
        "currency": None,
        "line_items": [],
    }


def test_line_items_with_nothing_readable_are_dropped() -> None:
    parsed = parse_expense_response(
        response([], [[summary("EXPENSE_ROW", "subtotal")], [summary("ITEM", "Real")]])
    )
    assert [item["name"] for item in parsed["line_items"]] == ["Real"]


def test_no_expense_document_is_a_failure() -> None:
    """The one real error: Textract could not see a receipt at all."""
    with pytest.raises(OcrError):
        parse_expense_response({"ExpenseDocuments": []})
