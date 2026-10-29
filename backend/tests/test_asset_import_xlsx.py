"""Bulk import from .xlsx (CLOUDAPPG5-93).

README.md scopes Leg A as "bulk import (**CSV/Excel**)" and docs/api.md calls
the endpoint "Bulk CSV/Excel import", so both formats are in scope. `.xls` is
named nowhere in the project and is not supported.

The point of these tests is that **Excel must behave exactly like the CSV of
the same sheet**. Both formats are reduced to the same rows before any rule
runs, so the interesting cases are the ones where a spreadsheet does something
a text file cannot: real date cells, numeric cells, formulas, and the hundreds
of blank rows Excel keeps because somebody once clicked there.

`test_xlsx_and_csv_of_the_same_sheet_agree` is the one that holds the whole
thing together.
"""

from __future__ import annotations

import csv
import datetime
import io

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.services.asset_import import COLUMNS

HEADER = list(COLUMNS)


def values(**overrides: object) -> dict[str, object]:
    row = {
        "name": "Dell Latitude 5540",
        "serial_number": "ABC123",
        "condition": "new",
        "purchase_date": "2025-03-01",
        "price": "32900.00",
        "currency": "THB",
        "invoice_number": "INV-2025-001",
        "vendor": "Power Buy",
        "category": "Laptop",
        "department": "",
        "location": "",
        "storage_note": "",
        "warranty_provider": "Dell",
        "warranty_start_date": "2025-03-01",
        "warranty_duration_months": "36",
    }
    row.update(overrides)
    return row


def xlsx_bytes(
    rows: list[dict[str, object]],
    header: list[str] | None = None,
    *,
    trailing_blanks: int = 0,
) -> bytes:
    book = Workbook()
    sheet = book.active
    names = header or HEADER
    sheet.append(names)
    for row in rows:
        sheet.append([row.get(name, "") for name in names])
    for _ in range(trailing_blanks):
        sheet.append([None] * len(names))

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def csv_bytes(rows: list[dict[str, object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADER)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in HEADER})
    return buffer.getvalue().encode("utf-8")


def post(api: TestClient, payload: bytes, mode: str = "validate"):
    return api.post(f"/assets/import?mode={mode}", content=payload)


# --- the format is detected, not declared -----------------------------------


def test_an_xlsx_file_is_recognised(api: TestClient) -> None:
    """No Content-Type and no filename — the bytes say what it is."""
    response = post(api, xlsx_bytes([values()]))

    assert response.status_code == 200
    assert response.json() == {"total_rows": 1, "valid": 1, "errors": []}


def test_an_xlsx_commit_creates_the_rows(api: TestClient) -> None:
    response = post(
        api,
        xlsx_bytes([values(), values(serial_number="DEF456")]),
        mode="commit",
    )

    assert response.json()["created"] == 2
    assert api.get("/assets").json()["total"] == 2


def test_a_corrupt_xlsx_is_a_file_level_error(api: TestClient) -> None:
    """Starts like a zip but is not a workbook."""
    response = post(api, b"PK\x03\x04 and then nonsense")

    assert response.status_code == 422
    assert ".xlsx" in response.json()["detail"]


# --- things a spreadsheet does that a text file cannot ----------------------


def test_a_real_date_cell_is_read_as_a_date(api: TestClient) -> None:
    """Excel stores dates as dates, not text.

    `str()` on one gives "2025-03-01 00:00:00", which Pydantic rejects. If
    this regresses, every .xlsx import fails on purchase_date.
    """
    response = post(
        api,
        xlsx_bytes(
            [
                values(
                    purchase_date=datetime.date(2025, 3, 1),
                    warranty_start_date=datetime.datetime(2025, 3, 1, 9, 30),
                )
            ]
        ),
    )

    assert response.json() == {"total_rows": 1, "valid": 1, "errors": []}


def test_a_numeric_duration_cell_is_read_as_a_number(api: TestClient) -> None:
    """A user types 36; Excel stores 36.0."""
    response = post(
        api, xlsx_bytes([values(warranty_duration_months=36, price=32900)])
    )

    assert response.json()["valid"] == 1


def test_a_numeric_price_keeps_its_value(api: TestClient) -> None:
    created = post(
        api, xlsx_bytes([values(price=51599)]), mode="commit"
    ).json()

    assert created["created"] == 1
    asset = api.get("/assets").json()["items"][0]
    detail = api.get(f"/assets/{asset['id']}").json()
    assert detail["price"] == "51599.00"


def test_trailing_blank_rows_are_ignored(api: TestClient) -> None:
    """Excel keeps rows somebody once clicked on.

    Without this, a two-row sheet reports two hundred "Field required"
    errors and the user cannot find the real one.
    """
    response = post(api, xlsx_bytes([values()], trailing_blanks=50))

    assert response.json() == {"total_rows": 1, "valid": 1, "errors": []}


def test_only_the_first_worksheet_is_read(api: TestClient) -> None:
    """A second tab is far more likely to be notes than more assets."""
    book = Workbook()
    sheet = book.active
    sheet.append(HEADER)
    sheet.append([values().get(name, "") for name in HEADER])
    notes = book.create_sheet("Notes")
    notes.append(["ignore", "me"])
    buffer = io.BytesIO()
    book.save(buffer)

    assert post(api, buffer.getvalue()).json()["total_rows"] == 1


# --- the same rules, whichever format ---------------------------------------


def test_xlsx_and_csv_of_the_same_sheet_agree(api: TestClient) -> None:
    """The test this file exists for.

    The same three rows — one good, one broken, one duplicate — must produce
    the same verdict either way. A rule that holds for CSV and quietly not for
    Excel is the failure mode worth guarding.
    """
    rows = [
        values(serial_number="A1"),
        values(serial_number="A2", purchase_date="not-a-date", price="-5"),
        values(serial_number="A1", name="Duplicate"),
    ]

    from_csv = post(api, csv_bytes(rows)).json()
    from_xlsx = post(api, xlsx_bytes(rows)).json()

    assert from_csv == from_xlsx
    assert from_csv["valid"] == 1


def test_a_missing_required_column_is_rejected_in_xlsx_too(
    api: TestClient,
) -> None:
    header = [name for name in HEADER if name != "invoice_number"]

    response = post(api, xlsx_bytes([values()], header=header))

    assert response.status_code == 422
    assert "invoice_number" in response.json()["detail"]


def test_an_xlsx_dry_run_writes_nothing(api: TestClient) -> None:
    post(api, xlsx_bytes([values()]))

    assert api.get("/assets").json()["total"] == 0


def test_an_employee_may_not_import_an_xlsx_either(
    api: TestClient, db, membership
) -> None:
    from app.models.membership import MembershipRole

    membership.role = MembershipRole.employee
    db.flush()

    assert post(api, xlsx_bytes([values()]), mode="commit").status_code == 403
