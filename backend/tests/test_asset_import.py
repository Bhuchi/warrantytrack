"""Bulk asset import from CSV (CLOUDAPPG5-93).

The point of this feature is that it has **no rules of its own**. Every row
goes through `AssetCreate` and `asset_validation` — the pair `POST /assets`
and Leg B's OCR confirm already use — so a row rejected here is rejected for
the same reason and with the same wording. `test_a_row_is_judged_exactly_like_
a_single_post` is the test that holds that true.

Shape from docs/api.md:

    mode=validate  -> {total_rows, valid, errors[{row, field, message}]}
    mode=commit    -> {created, skipped}

Row numbers count the header as row 1, so the number in an error is the row
the user sees in their own spreadsheet.
"""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.catalog import Category, Vendor
from app.models.membership import Membership, MembershipRole
from app.models.workspace import Workspace
from app.services.asset_import import COLUMNS, MAX_ROWS

HEADER = list(COLUMNS)


def row(**overrides: str) -> dict[str, str]:
    """A complete, valid row. Overrides replace or blank single cells."""
    values = {
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
    values.update(overrides)
    return values


def csv_bytes(rows: list[dict[str, str]], header: list[str] | None = None) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header or HEADER)
    writer.writeheader()
    for entry in rows:
        writer.writerow({key: entry.get(key, "") for key in (header or HEADER)})
    return buffer.getvalue().encode("utf-8")


def post(api: TestClient, payload: bytes, mode: str = "validate"):
    return api.post(
        f"/assets/import?mode={mode}",
        content=payload,
        headers={"Content-Type": "text/csv"},
    )


def errors_for(response) -> list[tuple[int, str, str]]:
    return [
        (entry["row"], entry["field"], entry["message"])
        for entry in response.json()["errors"]
    ]


# --- the happy path ---------------------------------------------------------


def test_a_valid_file_validates_clean(api: TestClient) -> None:
    response = post(api, csv_bytes([row(), row(serial_number="DEF456")]))

    assert response.status_code == 200
    assert response.json() == {"total_rows": 2, "valid": 2, "errors": []}


def test_validate_writes_nothing(api: TestClient, db: Session) -> None:
    """A dry run is a dry run — including the vendor a name would create."""
    post(api, csv_bytes([row()]))

    assert db.scalars(select(Asset)).all() == []
    assert db.scalars(select(Vendor)).all() == []


def test_commit_creates_the_rows(api: TestClient) -> None:
    response = post(
        api, csv_bytes([row(), row(serial_number="DEF456")]), mode="commit"
    )

    assert response.status_code == 200
    assert response.json()["created"] == 2
    assert api.get("/assets").json()["total"] == 2


def test_commit_creates_the_catalog_rows_the_names_refer_to(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """Names, not ids: a spreadsheet holds "Power Buy"."""
    post(api, csv_bytes([row()]), mode="commit")

    vendors = db.scalars(
        select(Vendor).where(Vendor.workspace_id == workspace.id)
    ).all()
    categories = db.scalars(
        select(Category).where(Category.workspace_id == workspace.id)
    ).all()
    assert [vendor.name for vendor in vendors] == ["Power Buy"]
    assert [category.name for category in categories] == ["Laptop"]


def test_the_warranty_columns_become_a_warranty(api: TestClient) -> None:
    post(api, csv_bytes([row()]), mode="commit")

    asset = api.get("/assets").json()["items"][0]
    detail = api.get(f"/assets/{asset['id']}").json()
    assert detail["warranty"]["provider"] == "Dell"
    assert detail["warranty"]["end_date"] == "2028-03-01"


# --- rows that fail ---------------------------------------------------------


@pytest.mark.parametrize(
    "column",
    [
        "name",
        "serial_number",
        "purchase_date",
        "price",
        "invoice_number",
        "vendor",
        "category",
    ],
)
def test_a_missing_required_value_names_its_column(
    api: TestClient, column: str
) -> None:
    """The error quotes the column the user left empty, not an internal name."""
    response = post(api, csv_bytes([row(**{column: ""})]))

    assert response.json()["valid"] == 0
    assert any(
        error_row == 2 and field == column for error_row, field, _ in errors_for(response)
    )


def test_a_blank_condition_is_accepted(api: TestClient) -> None:
    """Condition is optional since issue #34, so an empty cell is not an error."""
    response = post(api, csv_bytes([row(condition="")]))

    assert response.json() == {"total_rows": 1, "valid": 1, "errors": []}


def test_a_misspelled_condition_is_still_rejected(api: TestClient) -> None:
    """Optional is not "anything goes": a value must still be a real condition."""
    response = post(api, csv_bytes([row(condition="gud")]))

    assert response.json()["valid"] == 0
    assert any(field == "condition" for _, field, _ in errors_for(response))


@pytest.mark.parametrize("value", ["   ", "\t"])
def test_a_whitespace_only_serial_is_rejected(api: TestClient, value: str) -> None:
    response = post(api, csv_bytes([row(serial_number=value)]))

    assert response.json()["valid"] == 0
    assert any(field == "serial_number" for _, field, _ in errors_for(response))


def test_a_whitespace_only_invoice_number_is_rejected(api: TestClient) -> None:
    response = post(api, csv_bytes([row(invoice_number="   ")]))

    assert any(field == "invoice_number" for _, field, _ in errors_for(response))


@pytest.mark.parametrize(
    "value", ["not-a-date", "01/03/2025", "2025-13-01", "2025-02-30"]
)
def test_an_invalid_date_is_rejected(api: TestClient, value: str) -> None:
    """docs/api.md defines the rule as "must be a valid date (YYYY-MM-DD)"."""
    response = post(api, csv_bytes([row(purchase_date=value)]))

    assert any(field == "purchase_date" for _, field, _ in errors_for(response))


def test_a_negative_price_is_rejected(api: TestClient) -> None:
    response = post(api, csv_bytes([row(price="-500.00")]))

    assert any(field == "price" for _, field, _ in errors_for(response))


def test_a_missing_warranty_is_rejected(api: TestClient) -> None:
    """One clear error, not three — the three columns are blank together."""
    response = post(
        api,
        csv_bytes(
            [
                row(
                    warranty_provider="",
                    warranty_start_date="",
                    warranty_duration_months="",
                )
            ]
        ),
    )

    assert response.json()["valid"] == 0
    assert any(field.startswith("warranty") for _, field, _ in errors_for(response))


def test_a_warranty_error_names_the_spreadsheet_column(api: TestClient) -> None:
    """`warranty.provider` in the API is `warranty_provider` in the file."""
    response = post(api, csv_bytes([row(warranty_provider="")]))

    assert any(
        field == "warranty_provider" for _, field, _ in errors_for(response)
    )


# --- duplicates -------------------------------------------------------------


def test_a_serial_repeated_inside_the_file_is_a_duplicate(
    api: TestClient,
) -> None:
    """Invisible to the database until the first of the pair is written."""
    response = post(api, csv_bytes([row(), row(name="Second")]))

    assert response.json()["valid"] == 1
    assert (3, "serial_number", "duplicate") in errors_for(response)


def test_a_serial_already_in_the_database_is_a_duplicate(
    api: TestClient,
) -> None:
    post(api, csv_bytes([row()]), mode="commit")

    response = post(api, csv_bytes([row()]))

    assert response.json()["valid"] == 0
    assert (2, "serial_number", "duplicate") in errors_for(response)


def test_the_same_serial_in_another_workspace_is_not_a_duplicate(
    api: TestClient, db: Session, other_workspace: Workspace
) -> None:
    """Serials are unique per workspace, never globally."""
    db.add(
        Asset(
            workspace_id=other_workspace.id,
            name="Theirs",
            serial_number="ABC123",
            condition="new",
            purchase_date="2025-03-01",
            currency="THB",
        )
    )
    db.flush()

    assert post(api, csv_bytes([row()])).json()["valid"] == 1


# --- partial import ---------------------------------------------------------


def test_good_rows_survive_a_bad_one(api: TestClient) -> None:
    """The contract's own example: 47 created, 3 skipped out of 50."""
    response = post(
        api,
        csv_bytes(
            [
                row(serial_number="A1"),
                row(serial_number="A2", purchase_date="nonsense"),
                row(serial_number="A3"),
            ]
        ),
        mode="commit",
    )

    body = response.json()
    assert body["created"] == 2
    assert body["skipped"] == 1
    assert api.get("/assets").json()["total"] == 2


def test_commit_reports_what_went_wrong_too(api: TestClient) -> None:
    """Not in the contract's example, but a user needs to know."""
    response = post(
        api,
        csv_bytes([row(serial_number="A1"), row(serial_number="A2", price="-1")]),
        mode="commit",
    )

    assert any(field == "price" for _, field, _ in errors_for(response))


# --- whole-file problems ----------------------------------------------------


def test_a_missing_required_column_is_a_file_level_error(api: TestClient) -> None:
    """No row to blame, so a plain message rather than a row list."""
    header = [name for name in HEADER if name != "serial_number"]

    response = post(api, csv_bytes([row()], header=header))

    assert response.status_code == 422
    assert "serial_number" in response.json()["detail"]


def test_an_optional_column_may_be_left_out_entirely(api: TestClient) -> None:
    """A user who tracks no departments should not need an empty column."""
    header = [
        name for name in HEADER if name not in {"department", "location", "condition"}
    ]

    assert post(api, csv_bytes([row()], header=header)).json()["valid"] == 1


def test_a_header_only_file_has_no_rows(api: TestClient) -> None:
    response = post(api, csv_bytes([]))

    assert response.json() == {"total_rows": 0, "valid": 0, "errors": []}


def test_an_empty_body_is_rejected(api: TestClient) -> None:
    response = post(api, b"")

    assert response.status_code == 400


def test_a_file_that_is_not_utf8_is_rejected(api: TestClient) -> None:
    response = post(api, b"\xff\xfe\x00not utf-8")

    assert response.status_code == 422


def test_an_excel_byte_order_mark_is_tolerated(api: TestClient) -> None:
    """Excel writes a BOM when saving CSV; left in place it corrupts the
    first header and the user is blamed for a column they did include."""
    payload = "﻿".encode() + csv_bytes([row()])

    assert post(api, payload).json()["valid"] == 1


def test_too_many_rows_is_rejected(api: TestClient) -> None:
    rows = [row(serial_number=f"S{index}") for index in range(MAX_ROWS + 1)]

    response = post(api, csv_bytes(rows))

    assert response.status_code == 422
    assert str(MAX_ROWS) in response.json()["detail"]


# --- permissions ------------------------------------------------------------


def test_an_employee_may_not_import(
    api: TestClient, db: Session, membership: Membership
) -> None:
    """Bulk import is an organization administrator's job."""
    membership.role = MembershipRole.employee
    db.flush()

    response = post(api, csv_bytes([row()]), mode="commit")

    assert response.status_code == 403
    assert db.scalars(select(Asset)).all() == []


@pytest.mark.parametrize("role", [MembershipRole.owner, MembershipRole.admin])
def test_owners_and_admins_may_import(
    api: TestClient, db: Session, membership: Membership, role: MembershipRole
) -> None:
    membership.role = role
    db.flush()

    assert post(api, csv_bytes([row()])).status_code == 200


def test_an_unknown_mode_is_rejected(api: TestClient) -> None:
    """A typo must not silently commit."""
    response = api.post(
        "/assets/import?mode=comit",
        content=csv_bytes([row()]),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 422


# --- the rule that matters most ---------------------------------------------


def test_a_row_is_judged_exactly_like_a_single_post(api: TestClient) -> None:
    """Import owns no validation of its own.

    The same bad value, sent both ways, must be refused by both — otherwise
    the spreadsheet path has quietly grown its own rules.
    """
    single = api.post(
        "/assets",
        json={
            "name": "Dell",
            "serial_number": "   ",
            "condition": "new",
            "purchase_date": "2025-03-01",
            "price": "1.00",
            "vendor_name": "V",
            "category_name": "C",
            "invoice_number": "I-1",
            "warranty": {
                "provider": "P",
                "start_date": "2025-03-01",
                "duration_months": 12,
            },
        },
    )
    bulk = post(api, csv_bytes([row(serial_number="   ")]))

    assert single.status_code == 422
    assert bulk.json()["valid"] == 0
    assert any(field == "serial_number" for _, field, _ in errors_for(bulk))
