"""Tests for the dashboard aggregates (CLOUDAPPG5-130).

These need a database on purpose: the thing under test is a GROUP BY, and the
bug worth catching is an asset falling out of a count because of a join. Every
row written here is rolled back — see the `db_session` fixture.
"""

import uuid
from datetime import date, timedelta

import pytest

from app.models.asset import Asset, AssetCondition
from app.models.catalog import Department, Vendor
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.warranty import Warranty
from app.models.workspace import Workspace, WorkspaceType
from app.services import dashboard as dashboard_service
from app.services.warranty import WarrantyStatus

TODAY = date(2026, 10, 27)


@pytest.fixture
def workspace(db_session):
    """A workspace with two users: an owner and an employee."""
    ws = Workspace(name="Dashboard Co", type=WorkspaceType.organization)
    owner = User(cognito_sub=f"owner-{uuid.uuid4()}", email=f"owner-{uuid.uuid4()}@t.local")
    employee = User(cognito_sub=f"emp-{uuid.uuid4()}", email=f"emp-{uuid.uuid4()}@t.local")
    db_session.add_all([ws, owner, employee])
    db_session.flush()
    db_session.add_all(
        [
            Membership(user_id=owner.id, workspace_id=ws.id, role=MembershipRole.owner),
            Membership(
                user_id=employee.id, workspace_id=ws.id, role=MembershipRole.employee
            ),
        ]
    )
    db_session.flush()
    return ws, owner, employee


def _asset(db, ws, name, *, end_offset=None, department=None, vendor=None, assigned=None):
    """One asset, optionally with a warranty that lapses `end_offset` days out."""
    asset = Asset(
        workspace_id=ws.id,
        name=name,
        serial_number=f"SN-{uuid.uuid4()}",
        condition=AssetCondition.good,
        purchase_date=TODAY - timedelta(days=400),
        department_id=department.id if department else None,
        vendor_id=vendor.id if vendor else None,
        assigned_to_user_id=assigned.id if assigned else None,
    )
    db.add(asset)
    db.flush()
    if end_offset is not None:
        db.add(
            Warranty(
                workspace_id=ws.id,
                asset_id=asset.id,
                end_date=TODAY + timedelta(days=end_offset),
                provider="ACME",
            )
        )
        db.flush()
    return asset


def test_summary_counts_every_status_including_no_warranty(db_session, workspace):
    ws, _, _ = workspace
    _asset(db_session, ws, "active one", end_offset=90)
    _asset(db_session, ws, "active two", end_offset=31)      # just outside the window
    _asset(db_session, ws, "soon", end_offset=30)            # last day inside it
    _asset(db_session, ws, "soon today", end_offset=0)       # expires today
    _asset(db_session, ws, "expired", end_offset=-1)
    _asset(db_session, ws, "no warranty at all")             # no warranty row

    result = dashboard_service.summary(db_session, ws.id, TODAY)

    assert result["active"] == 2
    assert result["expiring_soon"] == 2
    assert result["expired"] == 1
    assert result["no_warranty"] == 1
    # The regression that matters: the outer join must not drop the
    # warranty-less asset from the total.
    assert result["total"] == 6


def test_summary_ignores_other_workspaces(db_session, workspace):
    """Tenant isolation, checked rather than assumed."""
    ws, _, _ = workspace
    other = Workspace(name="Someone Else", type=WorkspaceType.organization)
    db_session.add(other)
    db_session.flush()

    _asset(db_session, ws, "ours", end_offset=10)
    _asset(db_session, other, "theirs", end_offset=10)

    result = dashboard_service.summary(db_session, ws.id, TODAY)
    assert result["total"] == 1


def test_summary_groups_by_department_busiest_first(db_session, workspace):
    ws, _, _ = workspace
    it = Department(workspace_id=ws.id, name="IT")
    marketing = Department(workspace_id=ws.id, name="Marketing")
    db_session.add_all([it, marketing])
    db_session.flush()

    _asset(db_session, ws, "a", end_offset=90, department=it)
    _asset(db_session, ws, "b", end_offset=90, department=it)
    _asset(db_session, ws, "c", end_offset=90, department=marketing)
    _asset(db_session, ws, "no department", end_offset=90)

    result = dashboard_service.summary(db_session, ws.id, TODAY)

    assert [(d["name"], d["count"]) for d in result["by_department"]] == [
        ("IT", 2),
        ("Marketing", 1),
    ]
    # The departmentless asset is in `total` but not in the chart — documented
    # in the service, asserted here so nobody "fixes" it by inventing a label.
    assert result["total"] == 4
    assert sum(d["count"] for d in result["by_department"]) == 3


def test_employee_sees_only_their_own_assets(db_session, workspace):
    ws, owner, employee = workspace
    _asset(db_session, ws, "theirs", end_offset=10, assigned=employee)
    _asset(db_session, ws, "someone else's", end_offset=10, assigned=owner)
    _asset(db_session, ws, "unassigned", end_offset=10)

    everyone = dashboard_service.summary(db_session, ws.id, TODAY)
    just_them = dashboard_service.summary(
        db_session, ws.id, TODAY, assigned_to_user_id=employee.id
    )

    assert everyone["total"] == 3
    assert just_them["total"] == 1


def test_expiring_lists_the_window_soonest_first(db_session, workspace):
    ws, _, _ = workspace
    _asset(db_session, ws, "in 30 days", end_offset=30)
    _asset(db_session, ws, "in 2 days", end_offset=2)
    _asset(db_session, ws, "in 31 days", end_offset=31)   # outside the window
    _asset(db_session, ws, "already expired", end_offset=-5)
    _asset(db_session, ws, "no warranty")

    items = dashboard_service.expiring(db_session, ws.id, TODAY)

    assert [i["name"] for i in items] == ["in 2 days", "in 30 days"]
    assert all(i["status"] is WarrantyStatus.expiring_soon for i in items)


def test_expiring_window_can_be_widened_without_changing_status(db_session, workspace):
    """Asked for 60 days, a 45-day warranty is listed but still reports active.

    The window picks rows; it does not redefine what the word means.
    """
    ws, _, _ = workspace
    _asset(db_session, ws, "in 45 days", end_offset=45)

    assert dashboard_service.expiring(db_session, ws.id, TODAY) == []

    wider = dashboard_service.expiring(db_session, ws.id, TODAY, days=60)
    assert [i["name"] for i in wider] == ["in 45 days"]
    assert wider[0]["status"] is WarrantyStatus.active


def test_expiring_returns_vendor_and_department_names(db_session, workspace):
    ws, _, _ = workspace
    it = Department(workspace_id=ws.id, name="IT")
    vendor = Vendor(workspace_id=ws.id, name="Power Buy")
    db_session.add_all([it, vendor])
    db_session.flush()

    _asset(db_session, ws, "with both", end_offset=5, department=it, vendor=vendor)
    _asset(db_session, ws, "with neither", end_offset=6)

    items = dashboard_service.expiring(db_session, ws.id, TODAY)

    assert (items[0]["vendor"], items[0]["department"]) == ("Power Buy", "IT")
    # Optional on an asset, so the outer joins must yield None, not drop the row.
    assert (items[1]["vendor"], items[1]["department"]) == (None, None)
