"""GET /dashboard/summary and /dashboard/expiring (CLOUDAPPG5-130).

Driven through the API rather than the service, because the thing worth
protecting is the whole answer the D04 screen receives — the counts, the
employee scoping and the shapes together.

What matters here is not that a date comparison works but that no asset falls
out of a count because of a join: an asset with no warranty, no department or
no vendor must still be counted and still appear.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetCondition
from app.models.catalog import Department, Vendor
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.warranty import Warranty
from app.models.workspace import Workspace

# The routes read the real clock, so offsets are taken from today rather than a
# pinned date. The status rule itself is pinned and swept in
# test_warranty_status.py; here the window just has to be the live one.
TODAY = date.today()


def make_asset(
    db: Session,
    workspace: Workspace,
    name: str,
    *,
    end_offset: int | None = None,
    department: Department | None = None,
    vendor: Vendor | None = None,
    assigned_to: User | None = None,
) -> Asset:
    """One asset, with a warranty lapsing `end_offset` days out if given."""
    asset = Asset(
        workspace_id=workspace.id,
        name=name,
        serial_number=f"SN-{uuid.uuid4()}",
        condition=AssetCondition.good,
        purchase_date=TODAY - timedelta(days=400),
        department_id=department.id if department else None,
        vendor_id=vendor.id if vendor else None,
        assigned_to_user_id=assigned_to.id if assigned_to else None,
    )
    db.add(asset)
    db.flush()
    if end_offset is not None:
        db.add(
            Warranty(
                workspace_id=workspace.id,
                asset_id=asset.id,
                end_date=TODAY + timedelta(days=end_offset),
                provider="Dell",
            )
        )
        db.flush()
    return asset


# --- summary ---------------------------------------------------------------


def test_summary_counts_every_status(api: TestClient, db: Session, workspace: Workspace) -> None:
    make_asset(db, workspace, "active", end_offset=90)
    make_asset(db, workspace, "active edge", end_offset=31)   # just outside
    make_asset(db, workspace, "soon", end_offset=30)          # last day inside
    make_asset(db, workspace, "soon today", end_offset=0)     # expires today
    make_asset(db, workspace, "expired", end_offset=-1)
    make_asset(db, workspace, "no warranty")                  # no warranty row

    body = api.get("/dashboard/summary").json()

    assert body["active"] == 2
    assert body["expiring_soon"] == 2
    assert body["expired"] == 1
    assert body["no_warranty"] == 1
    # The regression that matters: the outer join must not drop the
    # warranty-less asset from the total.
    assert body["total"] == 6


def test_summary_ignores_other_workspaces(
    api: TestClient, db: Session, workspace: Workspace, other_workspace: Workspace
) -> None:
    """Tenant isolation, checked rather than assumed."""
    make_asset(db, workspace, "ours", end_offset=10)
    make_asset(db, other_workspace, "theirs", end_offset=10)

    assert api.get("/dashboard/summary").json()["total"] == 1


def test_summary_groups_by_department_busiest_first(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    it = Department(workspace_id=workspace.id, name="IT")
    marketing = Department(workspace_id=workspace.id, name="Marketing")
    db.add_all([it, marketing])
    db.flush()

    make_asset(db, workspace, "a", end_offset=90, department=it)
    make_asset(db, workspace, "b", end_offset=90, department=it)
    make_asset(db, workspace, "c", end_offset=90, department=marketing)
    make_asset(db, workspace, "no department", end_offset=90)

    body = api.get("/dashboard/summary").json()

    assert [(d["name"], d["count"]) for d in body["by_department"]] == [
        ("IT", 2),
        ("Marketing", 1),
    ]
    # The departmentless asset is in `total` but not in the chart. The API does
    # not invent an "Others" label; asserted so nobody "fixes" that by adding
    # one server-side.
    assert body["total"] == 4
    assert sum(d["count"] for d in body["by_department"]) == 3


def test_an_employee_sees_only_their_own_assets(
    api: TestClient, db: Session, workspace: Workspace, user: User, membership: Membership
) -> None:
    """Their dashboard is theirs, not the organization's."""
    colleague = User(cognito_sub=f"c-{uuid.uuid4()}", email=f"c-{uuid.uuid4()}@t.local")
    db.add(colleague)
    db.flush()

    make_asset(db, workspace, "theirs", end_offset=10, assigned_to=user)
    make_asset(db, workspace, "colleague's", end_offset=10, assigned_to=colleague)
    make_asset(db, workspace, "unassigned", end_offset=10)

    assert api.get("/dashboard/summary").json()["total"] == 3

    membership.role = MembershipRole.employee
    db.flush()
    assert api.get("/dashboard/summary").json()["total"] == 1


def test_a_caller_with_no_membership_gets_404(
    api: TestClient, db: Session, workspace: Workspace, membership: Membership
) -> None:
    """Not 403 — a 403 would confirm the workspace exists.

    Follows the pattern in test_asset_delete.py: take the membership away
    inside the test's own transaction, rather than leaning on whether the dev
    database happens to have been seeded.
    """
    make_asset(db, workspace, "ours", end_offset=10)
    db.delete(membership)
    db.flush()

    assert api.get("/dashboard/summary").status_code == 404
    assert api.get("/dashboard/expiring").status_code == 404


# --- expiring --------------------------------------------------------------


def test_expiring_lists_the_window_soonest_first(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    make_asset(db, workspace, "in 30 days", end_offset=30)
    make_asset(db, workspace, "in 2 days", end_offset=2)
    make_asset(db, workspace, "in 31 days", end_offset=31)      # outside
    make_asset(db, workspace, "already expired", end_offset=-5)
    make_asset(db, workspace, "no warranty")

    items = api.get("/dashboard/expiring").json()["items"]

    assert [i["name"] for i in items] == ["in 2 days", "in 30 days"]
    assert all(i["status"] == "expiring_soon" for i in items)


def test_a_wider_window_does_not_redefine_the_status(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """`days` picks rows; it does not change what a word means.

    Asked for 60 days, a 45-day warranty is listed but still reports `active`,
    because that is what the asset list and detail screens call it.
    """
    make_asset(db, workspace, "in 45 days", end_offset=45)

    assert api.get("/dashboard/expiring").json()["items"] == []

    wider = api.get("/dashboard/expiring", params={"days": 60}).json()["items"]
    assert [i["name"] for i in wider] == ["in 45 days"]
    assert wider[0]["status"] == "active"


def test_expiring_returns_names_and_tolerates_their_absence(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """vendor and department are optional on an asset, so both can be null."""
    it = Department(workspace_id=workspace.id, name="IT")
    vendor = Vendor(workspace_id=workspace.id, name="Power Buy")
    db.add_all([it, vendor])
    db.flush()

    make_asset(db, workspace, "with both", end_offset=5, department=it, vendor=vendor)
    make_asset(db, workspace, "with neither", end_offset=6)

    items = api.get("/dashboard/expiring").json()["items"]

    assert (items[0]["vendor"], items[0]["department"]) == ("Power Buy", "IT")
    # The outer joins must yield null, not drop the row.
    assert (items[1]["vendor"], items[1]["department"]) == (None, None)


@pytest.mark.parametrize("days", [0, 366, -1])
def test_the_window_is_bounded(api: TestClient, days: int) -> None:
    """One request cannot ask for the whole table."""
    assert api.get("/dashboard/expiring", params={"days": days}).status_code == 422


def test_expiring_ignores_other_workspaces(
    api: TestClient, db: Session, workspace: Workspace, other_workspace: Workspace
) -> None:
    make_asset(db, workspace, "ours", end_offset=5)
    make_asset(db, other_workspace, "theirs", end_offset=5)

    items = api.get("/dashboard/expiring").json()["items"]
    assert [i["name"] for i in items] == ["ours"]
