"""POST /assets.

Required fields follow the team's 18 Oct decision (docs/frontend-plan.md,
enforced in add-asset/draft.ts): name, vendor, purchase date, price, condition
and serial number. Everything else is optional.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.catalog import Category, Vendor
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.utils.dates import add_months


def body(**overrides: object) -> dict[str, object]:
    """A minimal valid POST /assets body, with overrides."""
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


# --- the happy path ---------------------------------------------------------


def test_creates_an_asset_and_returns_the_detail_shape(api: TestClient) -> None:
    response = api.post("/assets", json=body())

    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Dell Latitude 5540"
    assert created["serial_number"] == "ABC123"
    assert created["condition"] == "new"
    assert created["currency"] == "THB"
    assert created["vendor"]["name"] == "Power Buy"


def test_workspace_and_creator_come_from_the_request_not_the_body(
    api: TestClient, db: Session, workspace: Workspace, user: User
) -> None:
    """A caller must not be able to file an asset into another workspace."""
    created = api.post("/assets", json=body()).json()

    asset = db.get(Asset, created["id"])
    assert asset is not None
    assert asset.workspace_id == workspace.id
    assert asset.created_by_user_id == user.id


# --- vendor and category by name or id --------------------------------------


def test_vendor_name_creates_the_vendor_when_missing(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """The form sends free text, so the backend has to make the row."""
    api.post("/assets", json=body(vendor_name="Power Buy"))

    vendors = db.scalars(
        select(Vendor).where(Vendor.workspace_id == workspace.id)
    ).all()
    assert [vendor.name for vendor in vendors] == ["Power Buy"]


def test_vendor_name_reuses_an_existing_row(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    existing = Vendor(workspace_id=workspace.id, name="Power Buy")
    db.add(existing)
    db.flush()

    created = api.post("/assets", json=body()).json()

    assert created["vendor"]["id"] == str(existing.id)


def test_vendor_name_matching_ignores_case(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """OCR capitalisation varies; two spellings must not become two vendors.

    The unique constraint is case-sensitive, so without a case-insensitive
    lookup "power buy" would sit alongside "Power Buy" and the dashboard would
    count them separately.
    """
    existing = Vendor(workspace_id=workspace.id, name="Power Buy")
    db.add(existing)
    db.flush()

    created = api.post("/assets", json=body(vendor_name="power buy")).json()

    assert created["vendor"]["id"] == str(existing.id)
    assert created["vendor"]["name"] == "Power Buy"


def test_vendor_id_wins_over_vendor_name(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """Once a dropdown sends an id, a stale name beside it must not override."""
    chosen = Vendor(workspace_id=workspace.id, name="JIB")
    db.add(chosen)
    db.flush()

    created = api.post(
        "/assets", json=body(vendor_id=str(chosen.id), vendor_name="Power Buy")
    ).json()

    assert created["vendor"]["name"] == "JIB"


def test_category_name_also_finds_or_creates(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    api.post("/assets", json=body(category_name="Laptop"))

    categories = db.scalars(
        select(Category).where(Category.workspace_id == workspace.id)
    ).all()
    assert [category.name for category in categories] == ["Laptop"]


# --- the warranty end date --------------------------------------------------


def test_end_date_is_computed_from_start_plus_duration(api: TestClient) -> None:
    """The client never sends end_date; the backend works it out."""
    created = api.post(
        "/assets",
        json=body(
            warranty={
                "provider": "Dell",
                "start_date": "2025-03-01",
                "duration_months": 36,
            }
        ),
    ).json()

    assert created["warranty"]["end_date"] == "2028-03-01"
    assert created["warranty"]["provider"] == "Dell"


def test_end_date_rolls_over_like_the_form_does(api: TestClient) -> None:
    """31 Jan + 1 month has no 31 Feb, so it rolls into March.

    The form previews this value with JavaScript's setMonth, which rolls over.
    dateutil would clamp to 28 Feb instead, and the saved date would silently
    disagree with what the user was shown.
    """
    created = api.post(
        "/assets",
        json=body(
            warranty={"provider": None, "start_date": "2025-01-31", "duration_months": 1}
        ),
    ).json()

    assert created["warranty"]["end_date"] == "2025-03-03"
    assert created["warranty"]["end_date"] == add_months(date(2025, 1, 31), 1).isoformat()


def test_warranty_is_optional(api: TestClient) -> None:
    """The form sends warranty: null when the fields are left blank."""
    created = api.post("/assets", json=body(warranty=None)).json()

    assert created["warranty"] is None


# --- validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "missing", ["name", "serial_number", "condition", "purchase_date", "price"]
)
def test_required_fields_are_rejected_when_missing(
    api: TestClient, missing: str
) -> None:
    payload = body()
    del payload[missing]

    response = api.post("/assets", json=payload)

    assert response.status_code == 422


def test_vendor_is_required_by_either_route(api: TestClient) -> None:
    payload = body()
    del payload["vendor_name"]

    response = api.post("/assets", json=payload)

    assert response.status_code == 422


def test_blank_name_is_rejected(api: TestClient) -> None:
    assert api.post("/assets", json=body(name="")).status_code == 422


def test_duplicate_serial_in_the_same_workspace_is_409(api: TestClient) -> None:
    """What makes the bulk importer's "duplicate" error possible."""
    api.post("/assets", json=body())

    response = api.post("/assets", json=body(name="A different laptop"))

    assert response.status_code == 409
    assert "ABC123" in response.json()["detail"]


def test_the_same_serial_in_another_workspace_is_fine(
    api: TestClient, db: Session, other_workspace: Workspace
) -> None:
    """Serials are unique per workspace, never globally.

    Two organizations can legitimately own hardware with the same serial.
    """
    db.add(
        Asset(
            workspace_id=other_workspace.id,
            name="Theirs",
            serial_number="ABC123",
            condition="new",
            purchase_date=date(2025, 3, 1),
            currency="THB",
        )
    )
    db.flush()

    assert api.post("/assets", json=body()).status_code == 201


# --- documents --------------------------------------------------------------


def test_document_ids_are_linked_to_the_asset(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    document = Document(workspace_id=workspace.id, s3_key="ws/receipt.jpg")
    db.add(document)
    db.flush()

    created = api.post(
        "/assets", json=body(document_ids=[str(document.id)])
    ).json()

    assert [doc["id"] for doc in created["documents"]] == [str(document.id)]


def test_a_document_from_another_workspace_is_rejected(
    api: TestClient, db: Session, other_workspace: Workspace
) -> None:
    """Otherwise the detail screen would hand out a presigned URL to it."""
    theirs = Document(workspace_id=other_workspace.id, s3_key="theirs/receipt.jpg")
    db.add(theirs)
    db.flush()

    response = api.post("/assets", json=body(document_ids=[str(theirs.id)]))

    assert response.status_code == 422


def test_an_unknown_document_id_is_rejected(api: TestClient) -> None:
    response = api.post(
        "/assets", json=body(document_ids=["00000000-0000-0000-0000-0000000000ff"])
    )

    assert response.status_code == 422


# --- the new asset shows up in the list -------------------------------------


def test_a_created_asset_appears_in_the_list(api: TestClient) -> None:
    """End to end: POST then GET, the two halves of the wizard's save."""
    api.post(
        "/assets",
        json=body(
            category_name="Laptop",
            warranty={
                "provider": "Dell",
                "start_date": "2025-03-01",
                "duration_months": 120,
            },
        ),
    )

    item = api.get("/assets").json()["items"][0]

    assert item["name"] == "Dell Latitude 5540"
    assert item["category_name"] == "Laptop"
    assert item["vendor_name"] == "Power Buy"
    assert item["warranty_status"] == "active"
