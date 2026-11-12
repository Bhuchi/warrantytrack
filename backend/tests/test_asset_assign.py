"""POST /assets/{id}/assign — the admin's half of asset assignment.

The employee's half already works and is covered by
tests/test_asset_employee_scope.py: an employee sees and edits only the assets
assigned to them. What was missing was the action that puts an asset in their
hands in the first place.

One endpoint does assign, reassign and unassign, matching docs/api.md: "assign
/ unassign to an employee (admin only)", with `null` to unassign. Three
operations through one door cannot drift apart.

The failure codes carry different meanings and are tested as such:
403 you may not do this, 404 no such asset here, 422 that person cannot hold it.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceType

MANAGERS = [MembershipRole.owner, MembershipRole.admin]


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


def add_member(
    db: Session,
    workspace: Workspace,
    *,
    name: str,
    role: MembershipRole = MembershipRole.employee,
) -> User:
    """Another person in the workspace, with a membership."""
    user = User(
        cognito_sub=f"sub-{name}",
        email=f"{name}@warrantytrack.local",
        display_name=name.title(),
    )
    db.add(user)
    db.flush()
    db.add(Membership(user_id=user.id, workspace_id=workspace.id, role=role))
    db.flush()
    return user


# --- assigning --------------------------------------------------------------


def test_an_admin_can_assign_an_asset(
    api: TestClient, db: Session, workspace: Workspace, membership: Membership
) -> None:
    employee = add_member(db, workspace, name="dana")
    membership.role = MembershipRole.admin
    db.flush()
    asset = api.post("/assets", json=body()).json()

    response = api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(employee.id)},
    )

    assert response.status_code == 200
    assert response.json()["assigned_to"] == {
        "user_id": str(employee.id),
        "display_name": "Dana",
    }


@pytest.mark.parametrize("role", MANAGERS)
def test_owners_and_admins_may_both_assign(
    api: TestClient,
    db: Session,
    workspace: Workspace,
    membership: Membership,
    role: MembershipRole,
) -> None:
    employee = add_member(db, workspace, name="dana")
    asset = api.post("/assets", json=body()).json()
    membership.role = role
    db.flush()

    response = api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(employee.id)},
    )

    assert response.status_code == 200


def test_assigning_again_reassigns(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """Reassignment is the same call with a different id, not a separate one."""
    first = add_member(db, workspace, name="dana")
    second = add_member(db, workspace, name="eli")
    asset = api.post("/assets", json=body()).json()
    api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(first.id)},
    )

    response = api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(second.id)},
    )

    assert response.status_code == 200
    assert response.json()["assigned_to"]["user_id"] == str(second.id)


# --- unassigning ------------------------------------------------------------


def test_null_unassigns(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    employee = add_member(db, workspace, name="dana")
    asset = api.post("/assets", json=body()).json()
    api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(employee.id)},
    )

    response = api.post(
        f"/assets/{asset['id']}/assign", json={"assigned_to_user_id": None}
    )

    assert response.status_code == 200
    assert response.json()["assigned_to"] is None


def test_unassigning_does_not_delete_the_asset(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    """Taking an asset back is not throwing it away."""
    employee = add_member(db, workspace, name="dana")
    asset = api.post("/assets", json=body()).json()
    api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(employee.id)},
    )

    api.post(f"/assets/{asset['id']}/assign", json={"assigned_to_user_id": None})

    assert api.get(f"/assets/{asset['id']}").status_code == 200
    assert api.get("/assets").json()["total"] == 1


def test_an_empty_body_is_rejected(api: TestClient) -> None:
    """`{}` is a 422, not a silent unassign — giving an asset back is a choice."""
    asset = api.post("/assets", json=body()).json()

    response = api.post(f"/assets/{asset['id']}/assign", json={})

    assert response.status_code == 422
    assert "assigned_to_user_id" in fields_in(response)


# --- who may call it --------------------------------------------------------


def test_an_employee_may_not_assign(
    api: TestClient, db: Session, workspace: Workspace, membership: Membership
) -> None:
    """403, not 404: they belong here, they just do not hand assets around."""
    colleague = add_member(db, workspace, name="dana")
    asset = api.post("/assets", json=body()).json()
    membership.role = MembershipRole.employee
    db.flush()

    response = api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(colleague.id)},
    )

    assert response.status_code == 403


def test_an_employee_cannot_assign_an_asset_to_themselves(
    api: TestClient, db: Session, workspace: Workspace, user: User, membership: Membership
) -> None:
    """The obvious way to abuse this, refused before the asset is read."""
    asset = api.post("/assets", json=body()).json()
    membership.role = MembershipRole.employee
    db.flush()

    response = api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(user.id)},
    )

    assert response.status_code == 403
    db.expire_all()
    stored = db.get(Asset, uuid.UUID(asset["id"]))
    assert stored is not None
    assert stored.assigned_to_user_id is None


# --- who may receive it -----------------------------------------------------


def test_assigning_to_a_non_member_is_rejected(
    api: TestClient, db: Session
) -> None:
    stranger = User(
        cognito_sub="stranger-sub",
        email="stranger@warrantytrack.local",
        display_name="Stranger",
    )
    db.add(stranger)
    db.flush()
    asset = api.post("/assets", json=body()).json()

    response = api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(stranger.id)},
    )

    assert response.status_code == 422
    assert "assigned_to_user_id" in fields_in(response)


def test_assigning_to_a_member_of_another_workspace_is_rejected(
    api: TestClient, db: Session, other_workspace: Workspace
) -> None:
    """Being someone's employee elsewhere does not qualify you here."""
    outsider = add_member(db, other_workspace, name="outsider")
    asset = api.post("/assets", json=body()).json()

    response = api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(outsider.id)},
    )

    assert response.status_code == 422


def test_an_unknown_user_id_is_rejected(api: TestClient) -> None:
    asset = api.post("/assets", json=body()).json()

    response = api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": "00000000-0000-0000-0000-0000000000ff"},
    )

    assert response.status_code == 422


# --- which assets ------------------------------------------------------------


def test_assigning_an_asset_in_another_workspace_is_404(
    api: TestClient, db: Session, workspace: Workspace, other_workspace: Workspace
) -> None:
    employee = add_member(db, workspace, name="dana")
    theirs = Asset(
        workspace_id=other_workspace.id,
        name="Theirs",
        serial_number="THEIRS-1",
        condition="new",
        purchase_date="2025-03-01",
        currency="THB",
    )
    db.add(theirs)
    db.flush()

    response = api.post(
        f"/assets/{theirs.id}/assign",
        json={"assigned_to_user_id": str(employee.id)},
    )

    assert response.status_code == 404
    db.expire_all()
    assert theirs.assigned_to_user_id is None


def test_assigning_an_unknown_asset_is_404(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    employee = add_member(db, workspace, name="dana")

    response = api.post(
        "/assets/00000000-0000-0000-0000-0000000000ff/assign",
        json={"assigned_to_user_id": str(employee.id)},
    )

    assert response.status_code == 404


# --- what the employee sees afterwards --------------------------------------


def test_the_assignee_can_then_see_the_asset(
    api: TestClient, db: Session, workspace: Workspace, user: User, membership: Membership
) -> None:
    """Assignment is what brings an asset into an employee's scope."""
    asset = api.post("/assets", json=body()).json()
    api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(user.id)},
    )
    membership.role = MembershipRole.employee
    db.flush()

    assert api.get("/assets").json()["total"] == 1
    assert api.get(f"/assets/{asset['id']}").status_code == 200


def test_after_unassigning_the_former_assignee_loses_sight_of_it(
    api: TestClient, db: Session, workspace: Workspace, user: User, membership: Membership
) -> None:
    asset = api.post("/assets", json=body()).json()
    api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(user.id)},
    )
    api.post(f"/assets/{asset['id']}/assign", json={"assigned_to_user_id": None})
    membership.role = MembershipRole.employee
    db.flush()

    assert api.get("/assets").json()["total"] == 0
    assert api.get(f"/assets/{asset['id']}").status_code == 404


def test_a_rejected_assignment_changes_nothing(
    api: TestClient, db: Session, workspace: Workspace
) -> None:
    employee = add_member(db, workspace, name="dana")
    asset = api.post("/assets", json=body()).json()
    api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": str(employee.id)},
    )

    api.post(
        f"/assets/{asset['id']}/assign",
        json={"assigned_to_user_id": "00000000-0000-0000-0000-0000000000ff"},
    )

    db.expire_all()
    stored = db.get(Asset, uuid.UUID(asset["id"]))
    assert stored is not None
    assert stored.assigned_to_user_id == employee.id
