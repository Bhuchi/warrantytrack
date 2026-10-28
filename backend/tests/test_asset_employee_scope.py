"""Employees see and touch only the assets assigned to them.

The second of the two checks in docs/architecture.md: `workspace_id` keeps
tenants apart, and this keeps an employee inside their own slice of one
workspace. `assets.assigned_to_user_id` is annotated "employees see only
these" in docs/erd.md, and the Asset model says the same.

Owners and admins are deliberately covered too. A scoping bug that hides
assets from an admin is as bad as one that shows them to an employee, and only
testing the employee path would catch half of them.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace

MANAGERS = [MembershipRole.owner, MembershipRole.admin]


def make_asset(
    db: Session,
    workspace: Workspace,
    *,
    name: str,
    serial_number: str,
    assigned_to: User | None = None,
) -> Asset:
    asset = Asset(
        workspace_id=workspace.id,
        name=name,
        serial_number=serial_number,
        condition="new",
        purchase_date=date(2025, 3, 1),
        currency="THB",
        assigned_to_user_id=assigned_to.id if assigned_to else None,
    )
    db.add(asset)
    db.flush()
    return asset


@pytest.fixture
def colleague(db: Session) -> User:
    """Somebody else in the same workspace, to own the assets we must not see."""
    colleague = User(
        cognito_sub="colleague-sub",
        email="colleague@warrantytrack.local",
        display_name="Colleague",
    )
    db.add(colleague)
    db.flush()
    return colleague


# --- GET /assets ------------------------------------------------------------


def test_employee_lists_only_their_own_assets(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    user: User,
    colleague: User,
    membership: Membership,
) -> None:
    make_asset(db, workspace, name="Mine", serial_number="M1", assigned_to=user)
    make_asset(db, workspace, name="Theirs", serial_number="T1", assigned_to=colleague)
    make_asset(db, workspace, name="Unassigned", serial_number="U1")
    membership.role = MembershipRole.employee
    db.flush()

    body = api.get("/assets").json()

    assert [item["name"] for item in body["items"]] == ["Mine"]


def test_employee_total_counts_only_their_own(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    user: User,
    colleague: User,
    membership: Membership,
) -> None:
    """`total` drives "1-20 of N", so it has to be scoped as well as the page.

    If only the page were filtered, an employee with one asset would be told
    the organization's number instead of their own.
    """
    make_asset(db, workspace, name="Mine", serial_number="M1", assigned_to=user)
    for index in range(3):
        make_asset(
            db,
            workspace,
            name=f"Theirs {index}",
            serial_number=f"T{index}",
            assigned_to=colleague,
        )
    membership.role = MembershipRole.employee
    db.flush()

    assert api.get("/assets").json()["total"] == 1


@pytest.mark.parametrize("role", MANAGERS)
def test_managers_list_every_asset(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    user: User,
    colleague: User,
    membership: Membership,
    role: MembershipRole,
) -> None:
    make_asset(db, workspace, name="Mine", serial_number="M1", assigned_to=user)
    make_asset(db, workspace, name="Theirs", serial_number="T1", assigned_to=colleague)
    make_asset(db, workspace, name="Unassigned", serial_number="U1")
    membership.role = role
    db.flush()

    assert api.get("/assets").json()["total"] == 3


def test_scope_survives_the_other_filters(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    user: User,
    colleague: User,
    membership: Membership,
) -> None:
    """A search must not become a way around the scope."""
    make_asset(db, workspace, name="Dell laptop", serial_number="M1", assigned_to=user)
    make_asset(
        db, workspace, name="Dell monitor", serial_number="T1", assigned_to=colleague
    )
    membership.role = MembershipRole.employee
    db.flush()

    body = api.get("/assets", params={"q": "Dell"}).json()

    assert [item["name"] for item in body["items"]] == ["Dell laptop"]


# --- GET /assets/{id} -------------------------------------------------------


def test_employee_cannot_read_an_asset_assigned_to_someone_else(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    colleague: User,
    membership: Membership,
) -> None:
    """404, not 403 — same reasoning as a cross-workspace read."""
    theirs = make_asset(
        db, workspace, name="Theirs", serial_number="T1", assigned_to=colleague
    )
    membership.role = MembershipRole.employee
    db.flush()

    assert api.get(f"/assets/{theirs.id}").status_code == 404


def test_employee_cannot_read_an_unassigned_asset(
    api: TestClient, db: Session, workspace: Workspace, membership: Membership
) -> None:
    """Not assigned to anyone is still not assigned to you."""
    orphan = make_asset(db, workspace, name="Unassigned", serial_number="U1")
    membership.role = MembershipRole.employee
    db.flush()

    assert api.get(f"/assets/{orphan.id}").status_code == 404


def test_employee_can_read_their_own_asset(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    user: User,
    membership: Membership,
) -> None:
    mine = make_asset(db, workspace, name="Mine", serial_number="M1", assigned_to=user)
    membership.role = MembershipRole.employee
    db.flush()

    response = api.get(f"/assets/{mine.id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Mine"


@pytest.mark.parametrize("role", MANAGERS)
def test_managers_can_read_any_asset(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    colleague: User,
    membership: Membership,
    role: MembershipRole,
) -> None:
    theirs = make_asset(
        db, workspace, name="Theirs", serial_number="T1", assigned_to=colleague
    )
    membership.role = role
    db.flush()

    assert api.get(f"/assets/{theirs.id}").status_code == 200


# --- PATCH ------------------------------------------------------------------


def test_employee_cannot_edit_an_asset_assigned_to_someone_else(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    colleague: User,
    membership: Membership,
) -> None:
    """docs/architecture.md says employees "may only touch" their own assets.

    Editing is touching, so PATCH fetches through the same scope as GET —
    there is no id an employee can reach here that they could not already
    read.
    """
    theirs = make_asset(
        db, workspace, name="Theirs", serial_number="T1", assigned_to=colleague
    )
    membership.role = MembershipRole.employee
    db.flush()

    response = api.patch(f"/assets/{theirs.id}", json={"name": "Hijacked"})

    assert response.status_code == 404
    assert theirs.name == "Theirs"


def test_employee_can_edit_their_own_asset(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    user: User,
    membership: Membership,
) -> None:
    mine = make_asset(db, workspace, name="Mine", serial_number="M1", assigned_to=user)
    membership.role = MembershipRole.employee
    db.flush()

    response = api.patch(f"/assets/{mine.id}", json={"location": "Shelf B2"})

    assert response.status_code == 200
    assert response.json()["location"] == "Shelf B2"


# --- the write paths must still be able to read back their own work ---------


def test_creating_an_unassigned_asset_still_returns_it(api: TestClient) -> None:
    """POST reads the asset back after committing, and must not be scoped.

    An owner creating an unassigned asset would otherwise write the row and
    then fail to read it, turning a successful create into a 500.
    """
    response = api.post(
        "/assets",
        json={
            "name": "Fresh",
            "serial_number": "F1",
            "condition": "new",
            "purchase_date": "2025-03-01",
            "price": "100.00",
            "vendor_name": "Power Buy",
        },
    )

    assert response.status_code == 201
    assert response.json()["assigned_to"] is None
