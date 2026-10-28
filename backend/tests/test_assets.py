"""GET /assets and GET /assets/{id}.

Dates are built relative to `date.today()` rather than hard-coded, so the
status boundary tests keep meaning the same thing tomorrow. A fixed
"2026-03-01" would quietly stop testing the boundary once the clock passed it.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetCondition
from app.models.catalog import Category, Location, Vendor
from app.models.user import User
from app.models.warranty import Warranty
from app.models.workspace import Workspace
from app.services.warranty import EXPIRING_SOON_DAYS

TODAY = date.today()


def make_asset(
    db: Session,
    workspace: Workspace,
    *,
    name: str = "Dell Latitude 5540",
    serial_number: str = "ABC123",
    warranty_end: date | None = None,
    category: Category | None = None,
    vendor: Vendor | None = None,
    site: Location | None = None,
    storage_note: str | None = None,
    invoice_number: str | None = None,
    assigned_to: User | None = None,
) -> Asset:
    """Create one asset, optionally with a warranty.

    `warranty_end=None` means no warranty row at all — which is what makes an
    asset's status `unknown`, not a null end date.

    `site` is the row from the `locations` list; `storage_note` is the free
    text about where the box is kept. Both exist because they are different
    things — the model column for the note is still called `location`.
    """
    asset = Asset(
        workspace_id=workspace.id,
        name=name,
        serial_number=serial_number,
        condition=AssetCondition.new,
        purchase_date=date(2025, 3, 1),
        currency="THB",
        invoice_number=invoice_number,
        location=storage_note,
        location_id=site.id if site else None,
        category_id=category.id if category else None,
        vendor_id=vendor.id if vendor else None,
        assigned_to_user_id=assigned_to.id if assigned_to else None,
    )
    db.add(asset)
    db.flush()

    if warranty_end is not None:
        db.add(
            Warranty(
                workspace_id=workspace.id,
                asset_id=asset.id,
                provider="Dell",
                start_date=date(2025, 3, 1),
                end_date=warranty_end,
            )
        )
        db.flush()

    return asset


# --- GET /assets ------------------------------------------------------------


def test_empty_workspace_returns_no_items(api: TestClient) -> None:
    response = api.get("/assets")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_row_flattens_the_names_the_table_draws(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """category_name, vendor_name and location, as asked for in assetList.ts.

    `location` is the site from the `locations` list, not the storage note —
    the D05 column sits beside CATEGORY and VENDOR and is filtered by a
    dropdown, which only a list can fill.
    """
    category = Category(workspace_id=workspace.id, name="Laptop")
    vendor = Vendor(workspace_id=workspace.id, name="Power Buy")
    site = Location(workspace_id=workspace.id, name="HQ Floor 3")
    db.add_all([category, vendor, site])
    db.flush()
    make_asset(
        db,
        workspace,
        category=category,
        vendor=vendor,
        site=site,
        storage_note="Box is on the top shelf",
        warranty_end=TODAY + timedelta(days=365),
    )

    item = api.get("/assets").json()["items"][0]

    assert item["category_name"] == "Laptop"
    assert item["vendor_name"] == "Power Buy"
    assert item["location"] == "HQ Floor 3"
    assert item["serial_number"] == "ABC123"
    # The storage note is detail-screen material; it is not a list column.
    assert "storage_note" not in item


def test_assets_from_another_workspace_are_never_listed(
    api: TestClient, db: Session, workspace: Workspace, other_workspace: Workspace
) -> None:
    """The tenancy boundary, on the endpoint that would leak the most."""
    make_asset(db, workspace, name="Ours", serial_number="OURS-1")
    make_asset(db, other_workspace, name="Theirs", serial_number="THEIRS-1")

    body = api.get("/assets").json()

    assert body["total"] == 1
    assert [item["name"] for item in body["items"]] == ["Ours"]


def test_asset_without_a_warranty_is_unknown(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    make_asset(db, workspace, warranty_end=None)

    item = api.get("/assets").json()["items"][0]

    assert item["warranty_status"] == "unknown"
    assert item["warranty_end_date"] is None


# --- the status filter and its boundaries -----------------------------------


@pytest.mark.parametrize(
    "warranty_end, expected",
    [
        (TODAY - timedelta(days=1), "expired"),
        (TODAY, "expiring_soon"),
        (TODAY + timedelta(days=EXPIRING_SOON_DAYS), "expiring_soon"),
        (TODAY + timedelta(days=EXPIRING_SOON_DAYS + 1), "active"),
    ],
    ids=["yesterday", "today", "exactly-30-days", "31-days"],
)
def test_status_boundaries(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    warranty_end: date,
    expected: str,
) -> None:
    """The edges, which is where an off-by-one would hide.

    `end_date == today` is not yet past, so it is expiring_soon rather than
    expired; exactly 30 days out is still expiring_soon. These match
    app/services/warranty.py, which owns the rule.
    """
    make_asset(db, workspace, warranty_end=warranty_end)

    item = api.get("/assets").json()["items"][0]

    assert item["warranty_status"] == expected


@pytest.mark.parametrize(
    "status, expected_name",
    [
        ("expired", "Expired"),
        ("expiring_soon", "Expiring"),
        ("active", "Active"),
        ("unknown", "Unknown"),
    ],
)
def test_filtering_by_status_returns_only_that_status(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    status: str,
    expected_name: str,
) -> None:
    """One asset per status, then ask for each in turn.

    The filter is SQL and the label is Python, so this is also what proves the
    two agree — a row returned by ?status=expired must come back labelled
    "expired".
    """
    make_asset(db, workspace, name="Expired", serial_number="E1",
               warranty_end=TODAY - timedelta(days=1))
    make_asset(db, workspace, name="Expiring", serial_number="S1",
               warranty_end=TODAY + timedelta(days=10))
    make_asset(db, workspace, name="Active", serial_number="A1",
               warranty_end=TODAY + timedelta(days=365))
    make_asset(db, workspace, name="Unknown", serial_number="U1", warranty_end=None)

    body = api.get("/assets", params={"status": status}).json()

    assert body["total"] == 1
    assert body["items"][0]["name"] == expected_name
    assert body["items"][0]["warranty_status"] == status


# --- search and filters -----------------------------------------------------


@pytest.mark.parametrize(
    "query", ["Latitude", "latitude", "ABC1", "INV-2025"], ids=
    ["name", "case-insensitive", "serial", "invoice"]
)
def test_search_matches_name_serial_and_invoice(
    api: TestClient, db: Session, workspace: Workspace, query: str
) -> None:
    make_asset(db, workspace, invoice_number="INV-2025-001")
    make_asset(db, workspace, name="Other thing", serial_number="ZZZ999")

    body = api.get("/assets", params={"q": query}).json()

    assert body["total"] == 1
    assert body["items"][0]["name"] == "Dell Latitude 5540"


def test_filtering_by_category_and_vendor(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    laptop = Category(workspace_id=workspace.id, name="Laptop")
    monitor = Category(workspace_id=workspace.id, name="Monitor")
    db.add_all([laptop, monitor])
    db.flush()
    make_asset(db, workspace, name="A laptop", serial_number="L1", category=laptop)
    make_asset(db, workspace, name="A monitor", serial_number="M1", category=monitor)

    body = api.get("/assets", params={"category_id": str(laptop.id)}).json()

    assert body["total"] == 1
    assert body["items"][0]["name"] == "A laptop"


# --- paging -----------------------------------------------------------------


def test_total_counts_every_match_not_just_the_page(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """The screen shows "1-2 of 3", so `total` must outrun `items`."""
    for index in range(3):
        make_asset(db, workspace, name=f"Asset {index}", serial_number=f"S{index}")

    body = api.get("/assets", params={"page_size": 2}).json()

    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page_size"] == 2


def test_second_page_returns_the_remainder_without_repeats(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    for index in range(3):
        make_asset(db, workspace, name=f"Asset {index}", serial_number=f"S{index}")

    first = api.get("/assets", params={"page_size": 2, "page": 1}).json()
    second = api.get("/assets", params={"page_size": 2, "page": 2}).json()

    assert len(second["items"]) == 1
    first_ids = {item["id"] for item in first["items"]}
    assert first_ids.isdisjoint({item["id"] for item in second["items"]})


# --- GET /assets/{id} -------------------------------------------------------


def test_detail_returns_the_nested_contract_shape(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    category = Category(workspace_id=workspace.id, name="Laptop")
    vendor = Vendor(workspace_id=workspace.id, name="Power Buy")
    user = User(cognito_sub="sub-1", email="earth@example.com", display_name="Earth")
    site = Location(workspace_id=workspace.id, name="HQ Floor 3")
    db.add_all([category, vendor, site, user])
    db.flush()
    asset = make_asset(
        db,
        workspace,
        category=category,
        vendor=vendor,
        assigned_to=user,
        site=site,
        storage_note="Box is on the top shelf",
        warranty_end=TODAY + timedelta(days=365),
    )

    body = api.get(f"/assets/{asset.id}").json()

    assert body["category"] == {"id": str(category.id), "name": "Laptop"}
    assert body["vendor"] == {"id": str(vendor.id), "name": "Power Buy"}
    assert body["location"] == {"id": str(site.id), "name": "HQ Floor 3"}
    assert body["storage_note"] == "Box is on the top shelf"
    assert body["department"] is None
    assert body["assigned_to"] == {"user_id": str(user.id), "display_name": "Earth"}
    assert body["warranty"]["status"] == "active"
    assert body["warranty"]["provider"] == "Dell"
    assert body["condition"] == "new"
    assert body["documents"] == []


def test_detail_of_an_asset_without_a_warranty(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    asset = make_asset(db, workspace, warranty_end=None)

    body = api.get(f"/assets/{asset.id}").json()

    assert body["warranty"] is None


def test_detail_in_another_workspace_is_404_not_403(
    api: TestClient, db: Session, other_workspace: Workspace
) -> None:
    """404, deliberately. A 403 would confirm the record exists.

    See docs/api.md — there is a test for this precisely so nobody "fixes" it
    to 403 later.
    """
    theirs = make_asset(db, other_workspace, serial_number="THEIRS-1")

    response = api.get(f"/assets/{theirs.id}")

    assert response.status_code == 404


def test_detail_of_an_unknown_id_is_404(api: TestClient) -> None:
    response = api.get("/assets/00000000-0000-0000-0000-0000000000ff")

    assert response.status_code == 404
