"""A committed asset must have every required field (CLOUDAPPG5-118).

The list comes from docs/database/WarrantyTrack-ERD-v1.2/README.md, under
"Explicit design decisions":

  line 35  "The final asset requires product name, purchase date, price,
            serial number, vendor, category, and invoice number ...
            invoice_number is NOT NULL and nonblank even on manual entry
            (OCR failure never bypasses business required fields)."
  line 36  "A committed asset must have 1..N warranties ... The old
            `No Warranty Info` status is no longer generated for valid
            committed assets. If existing UI shows it, update the frontend
            separately."

which that document traces to the kick-off report and Jira CLOUDAPPG5-116
and -118.

Two halves, because a rule that only applies on create is not a rule:

- **create** must refuse a submission missing any of them
- **update** must refuse to take one away afterwards

The second half also fixes a 500. `PATCH {"name": null}` used to set the
column to NULL, the flush raised an IntegrityError, and the caller got a 500 —
neither clear nor per-field, which is exactly what this ticket asks for.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.catalog import Category, Vendor

#: Every field the schema demands outright on create.
REQUIRED_ON_CREATE = [
    "name",
    "serial_number",
    "condition",
    "purchase_date",
    "price",
    "invoice_number",
    "warranty",
]

#: Required fields that PATCH must refuse to null out. Vendor and category are
#: handled separately — they are cleared through their `_id` field.
REQUIRED_ON_UPDATE = [
    "name",
    "serial_number",
    "condition",
    "purchase_date",
    "price",
    "invoice_number",
]


def body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Dell Latitude 5540",
        "serial_number": "ABC123",
        "condition": "new",
        "purchase_date": "2025-03-01",
        "price": "32900.00",
        "vendor_name": "Power Buy",
        "category_name": "Laptop",
        "invoice_number": "INV-2025-001",
        "warranty": {
            "provider": "Dell",
            "start_date": "2025-03-01",
            "duration_months": 36,
        },
    }
    payload.update(overrides)
    return payload


def fields_in(response) -> set[str]:
    return {entry["loc"][1] for entry in response.json()["detail"]}


# --- create -----------------------------------------------------------------


def test_a_complete_submission_is_accepted(api: TestClient) -> None:
    """The baseline: everything present, nothing rejected."""
    response = api.post("/assets", json=body())

    assert response.status_code == 201
    created = response.json()
    assert created["category"]["name"] == "Laptop"
    assert created["vendor"]["name"] == "Power Buy"
    assert created["invoice_number"] == "INV-2025-001"
    assert created["warranty"]["provider"] == "Dell"


@pytest.mark.parametrize("field", REQUIRED_ON_CREATE)
def test_omitting_a_required_field_is_rejected(
    api: TestClient, field: str
) -> None:
    payload = body()
    del payload[field]

    response = api.post("/assets", json=payload)

    assert response.status_code == 422
    assert field in fields_in(response)


@pytest.mark.parametrize("label", ["vendor", "category"])
def test_omitting_vendor_or_category_entirely_is_rejected(
    api: TestClient, label: str
) -> None:
    """Either an id or a name will do, but one of them must be there."""
    payload = body()
    del payload[f"{label}_name"]

    response = api.post("/assets", json=payload)

    assert response.status_code == 422
    assert f"{label}_id" in fields_in(response)


def test_missing_vendor_and_category_are_reported_together(
    api: TestClient,
) -> None:
    payload = body()
    del payload["vendor_name"]
    del payload["category_name"]

    response = api.post("/assets", json=payload)

    assert response.status_code == 422
    # Named per field, not reported against the body as a whole: a
    # model-level validator would give loc ["body"] and the form could not
    # show it inline.
    assert fields_in(response) == {"vendor_id", "category_id"}


def test_a_warranty_provider_is_required(api: TestClient) -> None:
    """"Warranty details, including provider" — the ticket, verbatim."""
    response = api.post(
        "/assets",
        json=body(warranty={"start_date": "2025-03-01", "duration_months": 36}),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_warranty_provider_is_rejected(
    api: TestClient, value: str
) -> None:
    response = api.post(
        "/assets",
        json=body(
            warranty={
                "provider": value,
                "start_date": "2025-03-01",
                "duration_months": 36,
            }
        ),
    )

    assert response.status_code == 422


def test_an_incomplete_submission_writes_nothing(
    api: TestClient, db: Session
) -> None:
    """No asset, no warranty, and no catalog row made from a name on the way.

    The atomicity requirement: if any required check fails, neither the asset
    nor its warranty is saved.
    """
    payload = body()
    del payload["invoice_number"]

    response = api.post("/assets", json=payload)

    assert response.status_code == 422
    assert db.scalars(select(Asset)).all() == []
    assert db.scalars(select(Vendor)).all() == []
    assert db.scalars(select(Category)).all() == []


# --- update: a required field cannot be taken away --------------------------


@pytest.mark.parametrize("field", REQUIRED_ON_UPDATE)
def test_patch_cannot_null_a_required_field(
    api: TestClient, db: Session, field: str
) -> None:
    """Previously a 500 from an IntegrityError; now a 422 naming the field."""
    created = api.post("/assets", json=body()).json()

    response = api.patch(f"/assets/{created['id']}", json={field: None})

    assert response.status_code == 422
    assert field in fields_in(response)


@pytest.mark.parametrize("label", ["vendor", "category"])
def test_patch_cannot_clear_vendor_or_category(
    api: TestClient, label: str
) -> None:
    created = api.post("/assets", json=body()).json()

    response = api.patch(f"/assets/{created['id']}", json={f"{label}_id": None})

    assert response.status_code == 422
    assert f"{label}_id" in fields_in(response)


def test_patch_cannot_remove_the_warranty(api: TestClient) -> None:
    created = api.post("/assets", json=body()).json()

    response = api.patch(f"/assets/{created['id']}", json={"warranty": None})

    assert response.status_code == 422
    assert api.get(f"/assets/{created['id']}").json()["warranty"] is not None


def test_a_rejected_patch_changes_nothing(
    api: TestClient, db: Session
) -> None:
    """A valid field alongside an invalid one must not sneak through."""
    created = api.post("/assets", json=body()).json()

    response = api.patch(
        f"/assets/{created['id']}",
        json={"name": "Renamed", "invoice_number": None},
    )

    assert response.status_code == 422
    db.expire_all()
    asset = db.get(Asset, uuid.UUID(created["id"]))
    assert asset is not None
    assert asset.name == "Dell Latitude 5540"


# --- update: the optional ones still behave ---------------------------------


@pytest.mark.parametrize(
    "field", ["storage_note", "department_id", "location_id", "image_key"]
)
def test_patch_can_still_clear_an_optional_field(
    api: TestClient, field: str
) -> None:
    """The rule must not spread to fields that were never required."""
    created = api.post("/assets", json=body(storage_note="Top shelf")).json()

    response = api.patch(f"/assets/{created['id']}", json={field: None})

    assert response.status_code == 200


def test_patch_leaves_omitted_required_fields_alone(api: TestClient) -> None:
    """Omitting is not clearing — the ordinary partial update still works."""
    created = api.post("/assets", json=body()).json()

    updated = api.patch(
        f"/assets/{created['id']}", json={"name": "Renamed"}
    ).json()

    assert updated["name"] == "Renamed"
    assert updated["invoice_number"] == "INV-2025-001"
    assert updated["warranty"]["provider"] == "Dell"
    assert updated["vendor"]["name"] == "Power Buy"
