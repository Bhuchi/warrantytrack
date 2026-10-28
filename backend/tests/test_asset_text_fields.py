"""Whitespace-only text is not a value (CLOUDAPPG5-118).

Task 4's acceptance criteria name two fields: "reject whitespace-only serial
numbers and invoice numbers". Both are checked here, together with the
distinction the spec implies between them and an optional note:

- **serial number** — required, so "   " is a missing value: 422.
- **invoice number** — optional, but if the user typed something it has to be
  something: "   " is 422, omitted or null is fine.
- **storage note** — optional free text where blank genuinely means absent, so
  "   " becomes null rather than an error. Telling someone off for leaving an
  optional note empty would be noise.

Validation is in the schema, so it runs before any database work and reports
one entry per bad field.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset

BLANK = ["", "   ", "\t", "\n  "]


def body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Dell Latitude 5540",
        "serial_number": "ABC123",
        "condition": "new",
        "purchase_date": "2025-03-01",
        "price": "32900.00",
        "vendor_name": "Power Buy",
    }
    payload.update(overrides)
    return payload


def fields_in(response) -> set[str]:
    return {entry["loc"][1] for entry in response.json()["detail"]}


# --- serial number: required -----------------------------------------------


@pytest.mark.parametrize("value", BLANK)
def test_a_blank_serial_number_is_rejected(api: TestClient, value: str) -> None:
    response = api.post("/assets", json=body(serial_number=value))

    assert response.status_code == 422
    assert "serial_number" in fields_in(response)


def test_a_serial_number_is_stored_trimmed(
    api: TestClient, db: Session
) -> None:
    created = api.post("/assets", json=body(serial_number="  ABC123  ")).json()

    assert created["serial_number"] == "ABC123"
    stored = db.get(Asset, uuid.UUID(created["id"]))
    assert stored is not None
    assert stored.serial_number == "ABC123"


def test_trimming_makes_two_serials_collide(api: TestClient) -> None:
    """" ABC123 " and "ABC123" are the same serial, so the second is a 409.

    Without trimming before the uniqueness check, a workspace could hold two
    assets whose serials look identical on screen.
    """
    api.post("/assets", json=body(serial_number="ABC123"))

    response = api.post(
        "/assets", json=body(name="Second", serial_number="  ABC123  ")
    )

    assert response.status_code == 409


# --- invoice number: optional, but not blank --------------------------------


@pytest.mark.parametrize("value", BLANK)
def test_a_blank_invoice_number_is_rejected(api: TestClient, value: str) -> None:
    """The acceptance criterion, verbatim."""
    response = api.post("/assets", json=body(invoice_number=value))

    assert response.status_code == 422
    assert "invoice_number" in fields_in(response)


def test_an_omitted_invoice_number_is_fine(api: TestClient) -> None:
    response = api.post("/assets", json=body())

    assert response.status_code == 201
    assert response.json()["invoice_number"] is None


def test_an_explicitly_null_invoice_number_is_fine(api: TestClient) -> None:
    response = api.post("/assets", json=body(invoice_number=None))

    assert response.status_code == 201


def test_an_invoice_number_is_stored_trimmed(api: TestClient) -> None:
    created = api.post(
        "/assets", json=body(invoice_number="  INV-2025-001  ")
    ).json()

    assert created["invoice_number"] == "INV-2025-001"


def test_a_blank_invoice_number_is_rejected_on_patch(api: TestClient) -> None:
    created = api.post("/assets", json=body(invoice_number="INV-1")).json()

    response = api.patch(f"/assets/{created['id']}", json={"invoice_number": "  "})

    assert response.status_code == 422
    assert api.get(f"/assets/{created['id']}").json()["invoice_number"] == "INV-1"


def test_patch_can_still_clear_the_invoice_number_with_null(
    api: TestClient,
) -> None:
    """Rejecting "   " must not also block the way to clear the field."""
    created = api.post("/assets", json=body(invoice_number="INV-1")).json()

    updated = api.patch(f"/assets/{created['id']}", json={"invoice_number": None})

    assert updated.status_code == 200
    assert updated.json()["invoice_number"] is None


# --- storage note: blank means absent ---------------------------------------


@pytest.mark.parametrize("value", BLANK)
def test_a_blank_storage_note_becomes_null(api: TestClient, value: str) -> None:
    """Not an error — an empty optional note is just an empty optional note."""
    response = api.post("/assets", json=body(storage_note=value))

    assert response.status_code == 201
    assert response.json()["storage_note"] is None


def test_a_storage_note_is_stored_trimmed(api: TestClient) -> None:
    created = api.post(
        "/assets", json=body(storage_note="  Box is on the top shelf  ")
    ).json()

    assert created["storage_note"] == "Box is on the top shelf"


# --- the asset name ---------------------------------------------------------


@pytest.mark.parametrize("value", BLANK)
def test_a_blank_name_is_rejected(api: TestClient, value: str) -> None:
    response = api.post("/assets", json=body(name=value))

    assert response.status_code == 422
    assert "name" in fields_in(response)


# --- nothing is written when any of them fails ------------------------------


def test_a_rejected_text_field_writes_nothing(
    api: TestClient, db: Session
) -> None:
    """Schema validation runs before the route body, so there is no half-save.

    `vendor_name` here would otherwise create a catalog row on the way past.
    """
    response = api.post(
        "/assets", json=body(invoice_number="   ", vendor_name="Brand New Vendor")
    )

    assert response.status_code == 422
    assert db.scalars(select(Asset)).all() == []


def test_several_blank_fields_are_reported_together(api: TestClient) -> None:
    response = api.post(
        "/assets", json=body(name="  ", serial_number="  ", invoice_number="  ")
    )

    assert response.status_code == 422
    assert fields_in(response) == {"name", "serial_number", "invoice_number"}
