"""PATCH /assets/{id}.

The thing worth testing hardest is what PATCH means: a field the client did
not send must come back unchanged, while a field sent as null must be cleared.
Getting that wrong is invisible until someone edits one field and silently
wipes four others.
"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.catalog import Vendor
from app.models.workspace import Workspace


def create(api: TestClient, **overrides: object) -> dict:
    """An asset to edit, created through the API so it is fully populated."""
    payload: dict[str, object] = {
        "name": "Dell Latitude 5540",
        "serial_number": "ABC123",
        "condition": "new",
        "purchase_date": "2025-03-01",
        "price": "32900.00",
        "vendor_name": "Power Buy",
        "invoice_number": "INV-2025-001",
        "storage_note": "Box is on the top shelf",
        "warranty": {
            "provider": "Dell",
            "start_date": "2025-03-01",
            "duration_months": 36,
        },
    }
    payload.update(overrides)
    return api.post("/assets", json=payload).json()


# --- partial semantics ------------------------------------------------------


def test_changes_only_the_field_sent(api: TestClient) -> None:
    asset = create(api)

    updated = api.patch(f"/assets/{asset['id']}", json={"name": "Renamed"}).json()

    assert updated["name"] == "Renamed"
    # Everything else survives untouched.
    assert updated["serial_number"] == "ABC123"
    assert updated["invoice_number"] == "INV-2025-001"
    assert updated["storage_note"] == "Box is on the top shelf"
    assert updated["price"] == "32900.00"
    assert updated["vendor"]["name"] == "Power Buy"
    assert updated["warranty"]["end_date"] == "2028-03-01"


def test_an_empty_patch_changes_nothing(api: TestClient) -> None:
    asset = create(api)

    updated = api.patch(f"/assets/{asset['id']}", json={}).json()

    assert updated == asset


def test_explicit_null_clears_a_field(api: TestClient) -> None:
    """Sending null is a real instruction, not the same as omitting it.

    If the service tested `value is not None` instead of reading which keys
    were sent, there would be no way to ever clear an invoice number.
    """
    asset = create(api)

    updated = api.patch(
        f"/assets/{asset['id']}", json={"invoice_number": None}
    ).json()

    assert updated["invoice_number"] is None
    assert updated["storage_note"] == "Box is on the top shelf"


# --- vendor and category ----------------------------------------------------


def test_vendor_name_moves_the_asset_to_another_vendor(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    asset = create(api)

    updated = api.patch(f"/assets/{asset['id']}", json={"vendor_name": "JIB"}).json()

    assert updated["vendor"]["name"] == "JIB"
    names = sorted(
        vendor.name
        for vendor in db.query(Vendor).filter(Vendor.workspace_id == workspace.id)
    )
    assert names == ["JIB", "Power Buy"]


def test_vendor_can_be_cleared(api: TestClient) -> None:
    asset = create(api)

    updated = api.patch(f"/assets/{asset['id']}", json={"vendor_id": None}).json()

    assert updated["vendor"] is None


# --- the warranty -----------------------------------------------------------


def test_warranty_end_date_is_recomputed_on_update(api: TestClient) -> None:
    """A stored end date must never outlive the inputs it came from."""
    asset = create(api)

    updated = api.patch(
        f"/assets/{asset['id']}",
        json={
            "warranty": {
                "provider": "Dell Pro",
                "start_date": "2025-03-01",
                "duration_months": 12,
            }
        },
    ).json()

    assert updated["warranty"]["end_date"] == "2026-03-01"
    assert updated["warranty"]["provider"] == "Dell Pro"


def test_warranty_can_be_removed(api: TestClient) -> None:
    """An asset with no warranty is `unknown`, which is a valid state."""
    asset = create(api)

    updated = api.patch(f"/assets/{asset['id']}", json={"warranty": None}).json()

    assert updated["warranty"] is None
    assert api.get("/assets").json()["items"][0]["warranty_status"] == "unknown"


def test_warranty_can_be_added_to_an_asset_without_one(api: TestClient) -> None:
    asset = create(api, warranty=None)
    assert asset["warranty"] is None

    updated = api.patch(
        f"/assets/{asset['id']}",
        json={
            "warranty": {
                "provider": "Apple",
                "start_date": "2025-06-01",
                "duration_months": 24,
            }
        },
    ).json()

    assert updated["warranty"]["end_date"] == "2027-06-01"


# --- serial numbers ---------------------------------------------------------


def test_serial_can_be_changed(api: TestClient) -> None:
    asset = create(api)

    updated = api.patch(
        f"/assets/{asset['id']}", json={"serial_number": "XYZ789"}
    ).json()

    assert updated["serial_number"] == "XYZ789"


def test_resending_the_same_serial_is_not_a_conflict(api: TestClient) -> None:
    """The asset's own serial must not count as a clash with itself."""
    asset = create(api)

    response = api.patch(f"/assets/{asset['id']}", json={"serial_number": "ABC123"})

    assert response.status_code == 200


def test_taking_another_assets_serial_is_409(api: TestClient) -> None:
    first = create(api)
    create(api, name="Second", serial_number="XYZ789")

    response = api.patch(f"/assets/{first['id']}", json={"serial_number": "XYZ789"})

    assert response.status_code == 409


# --- tenancy and validation -------------------------------------------------


def test_patching_an_asset_in_another_workspace_is_404(
    api: TestClient, db: Session, other_workspace: Workspace
) -> None:
    """404 rather than 403 — a 403 would confirm the record exists."""
    theirs = Asset(
        workspace_id=other_workspace.id,
        name="Theirs",
        serial_number="THEIRS-1",
        condition="new",
        purchase_date=date(2025, 3, 1),
        currency="THB",
    )
    db.add(theirs)
    db.flush()

    response = api.patch(f"/assets/{theirs.id}", json={"name": "Hijacked"})

    assert response.status_code == 404
    assert theirs.name == "Theirs"


def test_patching_an_unknown_id_is_404(api: TestClient) -> None:
    response = api.patch(
        "/assets/00000000-0000-0000-0000-0000000000ff", json={"name": "Nope"}
    )

    assert response.status_code == 404


def test_a_blank_name_is_rejected(api: TestClient) -> None:
    asset = create(api)

    assert api.patch(f"/assets/{asset['id']}", json={"name": ""}).status_code == 422


def test_assignment_is_not_accepted_here(api: TestClient) -> None:
    """Assignment has its own admin-only endpoint; PATCH must not be a side door.

    Pydantic ignores unknown keys by default, so the field is simply not
    applied — this test is what would notice if it were ever added to
    AssetUpdate without the permission rules coming with it.
    """
    asset = create(api)

    updated = api.patch(
        f"/assets/{asset['id']}",
        json={"assigned_to_user_id": "00000000-0000-0000-0000-0000000000aa"},
    ).json()

    assert updated["assigned_to"] is None
