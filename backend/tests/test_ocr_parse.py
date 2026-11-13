"""Date, amount and currency readings in the OCR parser.

The model is asked for clean values but is not trusted: `parse_model_json`
puts every date and amount back through the same strict parsers, so a value
the model copied straight off the receipt becomes a clean field or an empty
one, never a wrong one. Pure functions; no AWS, no database.
"""

from __future__ import annotations

import pytest

from app.services.ocr import parse_model_json


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
    assert parse_model_json({"purchase_date": text})["purchase_date"] == expected


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
    assert parse_model_json({"total_amount": text})["total_amount"] == expected


@pytest.mark.parametrize(
    ("total_text", "expected"),
    [("฿100.00", "THB"), ("$100.00", "USD"), ("THB 100", "THB"), ("100.00", None)],
)
def test_currency_is_sniffed_from_the_total(total_text: str, expected: str | None) -> None:
    """With no currency from the model, the total's symbol or code decides."""
    assert parse_model_json({"total_amount": total_text})["currency"] == expected


def test_explicit_currency_wins() -> None:
    parsed = parse_model_json({"currency": "usd", "total_amount": "฿100.00"})
    assert parsed["currency"] == "USD"


def test_line_items_with_nothing_readable_are_dropped() -> None:
    parsed = parse_model_json({
        "line_items": [
            {"name": None, "price": None, "serial_number": None},
            {"name": "Dell Latitude 5540", "price": "32,900.00"},
        ]
    })
    assert [item["name"] for item in parsed["line_items"]] == ["Dell Latitude 5540"]
    assert parsed["line_items"][0]["price"] == "32900.00"
