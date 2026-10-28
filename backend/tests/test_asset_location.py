"""Attaching an asset to a site, and the storage note beside it.

Two different things that both used to be called "location":

- the **site**, a row in the `locations` list ("HQ Floor 3"). This is what the
  D05 table's LOCATION column shows — it sits between CATEGORY and VENDOR,
  both catalog lists, and its planned filter is a dropdown (AssetsList.tsx),
  which only a bounded list can fill.
- the **storage note**, free text about where the box is kept ("Box is on the
  top shelf"). The Add Asset form labels that field "Note"
  (BoxPhotoStep.tsx) and FE-11 calls it a free-text note.

The database column for the note is still `assets.location`; only the API
field was renamed, so no migration was needed.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.catalog import Location
from app.models.workspace import Workspace


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


# --- creating ---------------------------------------------------------------


def test_location_name_creates_the_site(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """Like vendor: a name the form sends becomes a row in the list."""
    created = api.post("/assets", json=body(location_name="HQ Floor 3")).json()

    assert created["location"]["name"] == "HQ Floor 3"
    sites = db.scalars(
        select(Location).where(Location.workspace_id == workspace.id)
    ).all()
    assert [site.name for site in sites] == ["HQ Floor 3"]


def test_location_name_reuses_an_existing_site(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    site = Location(workspace_id=workspace.id, name="HQ Floor 3")
    db.add(site)
    db.flush()

    created = api.post("/assets", json=body(location_name="hq floor 3")).json()

    assert created["location"]["id"] == str(site.id)
    assert created["location"]["name"] == "HQ Floor 3"


def test_location_id_is_accepted(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """What a real dropdown will send."""
    site = Location(workspace_id=workspace.id, name="HQ Floor 3")
    db.add(site)
    db.flush()

    created = api.post("/assets", json=body(location_id=str(site.id))).json()

    assert created["location"] == {"id": str(site.id), "name": "HQ Floor 3"}


def test_an_asset_can_have_no_site(api: TestClient) -> None:
    """Optional, like category and department."""
    created = api.post("/assets", json=body()).json()

    assert created["location"] is None


# --- the storage note -------------------------------------------------------


def test_storage_note_is_stored_and_returned(
    api: TestClient, db: Session
) -> None:
    created = api.post(
        "/assets", json=body(storage_note="Box is on the top shelf")
    ).json()

    assert created["storage_note"] == "Box is on the top shelf"
    stored = db.get(Asset, uuid.UUID(created["id"]))
    assert stored is not None
    # Still the `location` column underneath — renamed in the API only.
    assert stored.location == "Box is on the top shelf"


def test_the_site_and_the_note_are_independent(api: TestClient) -> None:
    """Both can be set, and they do not overwrite each other."""
    created = api.post(
        "/assets",
        json=body(location_name="HQ Floor 3", storage_note="Box is on the top shelf"),
    ).json()

    assert created["location"]["name"] == "HQ Floor 3"
    assert created["storage_note"] == "Box is on the top shelf"


# --- updating ---------------------------------------------------------------


def test_patch_moves_the_asset_to_another_site(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    created = api.post("/assets", json=body(location_name="HQ Floor 3")).json()

    updated = api.patch(
        f"/assets/{created['id']}", json={"location_name": "Warehouse"}
    ).json()

    assert updated["location"]["name"] == "Warehouse"


def test_patch_can_clear_the_site_without_touching_the_note(
    api: TestClient,
) -> None:
    created = api.post(
        "/assets",
        json=body(location_name="HQ Floor 3", storage_note="Box is on the top shelf"),
    ).json()

    updated = api.patch(
        f"/assets/{created['id']}", json={"location_id": None}
    ).json()

    assert updated["location"] is None
    assert updated["storage_note"] == "Box is on the top shelf"


def test_patch_can_clear_the_note_without_touching_the_site(
    api: TestClient,
) -> None:
    created = api.post(
        "/assets",
        json=body(location_name="HQ Floor 3", storage_note="Box is on the top shelf"),
    ).json()

    updated = api.patch(
        f"/assets/{created['id']}", json={"storage_note": None}
    ).json()

    assert updated["storage_note"] is None
    assert updated["location"]["name"] == "HQ Floor 3"


# --- the list ---------------------------------------------------------------


def test_the_list_shows_the_site_not_the_note(api: TestClient) -> None:
    """The D05 LOCATION column. A storage sentence does not belong in it."""
    api.post(
        "/assets",
        json=body(location_name="HQ Floor 3", storage_note="Box is on the top shelf"),
    )

    item = api.get("/assets").json()["items"][0]

    assert item["location"] == "HQ Floor 3"


def test_the_list_shows_nothing_when_there_is_no_site(api: TestClient) -> None:
    api.post("/assets", json=body(storage_note="Box is on the top shelf"))

    assert api.get("/assets").json()["items"][0]["location"] is None
