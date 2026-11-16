"""Cancel an invite, remove a member, leave an organization (GitHub #80)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.main import app
from app.models.asset import Asset, AssetCondition
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_invite import WorkspaceInvite


def make_member(db: Session, workspace: Workspace, role: MembershipRole) -> User:
    person = User(cognito_sub=f"m-{uuid.uuid4()}", email=f"{uuid.uuid4()}@example.com")
    db.add(person)
    db.flush()
    db.add(Membership(user_id=person.id, workspace_id=workspace.id, role=role))
    db.flush()
    return person


def act_as(person: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: person.id


def membership_of(db: Session, workspace: Workspace, person: User) -> Membership | None:
    return db.scalar(select(Membership).where(
        Membership.workspace_id == workspace.id, Membership.user_id == person.id
    ))


def assigned_asset(db: Session, workspace: Workspace, person: User) -> Asset:
    asset = Asset(
        workspace_id=workspace.id, name="Laptop", serial_number=f"SN-{uuid.uuid4()}",
        condition=AssetCondition.good, assigned_to_user_id=person.id,
        purchase_date=date(2026, 1, 15),
    )
    db.add(asset)
    db.flush()
    return asset


# --- cancel a pending invite ---------------------------------------------------


def test_owner_cancels_an_invite_case_insensitively(api: TestClient, db: Session, workspace: Workspace):
    assert api.post(f"/workspaces/{workspace.id}/members",
                    json={"email": "new@acme.com", "role": "employee"}).status_code == 201

    response = api.delete(f"/workspaces/{workspace.id}/invites", params={"email": "NEW@Acme.com"})

    assert response.status_code == 204
    assert db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.workspace_id == workspace.id)) is None
    assert api.delete(f"/workspaces/{workspace.id}/invites", params={"email": "new@acme.com"}).status_code == 404


def test_an_employee_may_not_cancel_an_invite(
    api: TestClient, db: Session, workspace: Workspace, user: User
):
    db.add(WorkspaceInvite(workspace_id=workspace.id, email="new@acme.com",
                           role=MembershipRole.employee, invited_by=user.id))
    act_as(make_member(db, workspace, MembershipRole.employee))

    response = api.delete(f"/workspaces/{workspace.id}/invites", params={"email": "new@acme.com"})

    assert response.status_code == 403
    assert db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.workspace_id == workspace.id)) is not None


def test_cancelling_needs_an_email(api: TestClient, workspace: Workspace):
    assert api.delete(f"/workspaces/{workspace.id}/invites").status_code == 422


# --- remove a member -----------------------------------------------------------


def test_admin_removes_an_employee_and_their_assets_are_unassigned(
    api: TestClient, db: Session, workspace: Workspace
):
    admin = make_member(db, workspace, MembershipRole.admin)
    employee = make_member(db, workspace, MembershipRole.employee)
    asset = assigned_asset(db, workspace, employee)
    act_as(admin)

    response = api.delete(f"/workspaces/{workspace.id}/members/{employee.id}")

    assert response.status_code == 204
    assert membership_of(db, workspace, employee) is None
    db.refresh(asset)
    assert asset.assigned_to_user_id is None


def test_nobody_removes_the_owner(api: TestClient, db: Session, workspace: Workspace, user: User):
    act_as(make_member(db, workspace, MembershipRole.admin))
    assert api.delete(f"/workspaces/{workspace.id}/members/{user.id}").status_code == 409
    assert membership_of(db, workspace, user) is not None


def test_removing_yourself_is_leave_not_remove(api: TestClient, db: Session, workspace: Workspace):
    admin = make_member(db, workspace, MembershipRole.admin)
    act_as(admin)
    assert api.delete(f"/workspaces/{workspace.id}/members/{admin.id}").status_code == 409


def test_an_employee_may_not_remove_anyone(api: TestClient, db: Session, workspace: Workspace):
    other = make_member(db, workspace, MembershipRole.employee)
    act_as(make_member(db, workspace, MembershipRole.employee))
    assert api.delete(f"/workspaces/{workspace.id}/members/{other.id}").status_code == 403


def test_removing_a_non_member_is_404(api: TestClient, other_workspace: Workspace, db: Session, workspace: Workspace):
    stranger = make_member(db, other_workspace, MembershipRole.employee)
    assert api.delete(f"/workspaces/{workspace.id}/members/{stranger.id}").status_code == 404


def test_only_assets_in_this_workspace_are_unassigned(
    api: TestClient, db: Session, workspace: Workspace, other_workspace: Workspace
):
    employee = make_member(db, workspace, MembershipRole.employee)
    db.add(Membership(user_id=employee.id, workspace_id=other_workspace.id, role=MembershipRole.employee))
    elsewhere = assigned_asset(db, other_workspace, employee)

    assert api.delete(f"/workspaces/{workspace.id}/members/{employee.id}").status_code == 204

    db.refresh(elsewhere)
    assert elsewhere.assigned_to_user_id == employee.id


# --- leave -----------------------------------------------------------------------


@pytest.mark.parametrize("role", [MembershipRole.admin, MembershipRole.employee])
def test_an_admin_or_employee_leaves(api: TestClient, db: Session, workspace: Workspace, role: MembershipRole):
    person = make_member(db, workspace, role)
    asset = assigned_asset(db, workspace, person)
    act_as(person)

    assert api.post(f"/workspaces/{workspace.id}/leave").status_code == 204

    assert membership_of(db, workspace, person) is None
    db.refresh(asset)
    assert asset.assigned_to_user_id is None
    # Gone means gone: the workspace is now a 404 for them.
    assert api.post(f"/workspaces/{workspace.id}/leave").status_code == 404


def test_the_owner_cannot_leave(api: TestClient, db: Session, workspace: Workspace, user: User):
    assert api.post(f"/workspaces/{workspace.id}/leave").status_code == 409
    assert membership_of(db, workspace, user) is not None


def test_nobody_leaves_a_personal_workspace(api: TestClient, db: Session, personal_workspace: Workspace, user: User):
    db.add(Membership(user_id=user.id, workspace_id=personal_workspace.id, role=MembershipRole.owner))
    db.flush()
    assert api.post(f"/workspaces/{personal_workspace.id}/leave").status_code == 422


def test_a_non_member_gets_404_everywhere(api: TestClient, db: Session, other_workspace: Workspace, user: User):
    base = f"/workspaces/{other_workspace.id}"
    assert api.post(f"{base}/leave").status_code == 404
    assert api.delete(f"{base}/members/{user.id}").status_code == 404
    assert api.delete(f"{base}/invites", params={"email": "x@example.com"}).status_code == 404


def test_signed_out_is_401(client: TestClient, workspace: Workspace):
    assert client.post(f"/workspaces/{workspace.id}/leave").status_code == 401


# --- delete an organization ------------------------------------------------------


def workspace_exists(db: Session, workspace_id: uuid.UUID) -> bool:
    db.expire_all()  # The route deleted rows in SQL; forget what the session cached.
    return db.get(Workspace, workspace_id) is not None


def test_the_owner_deletes_the_organization_and_everything_in_it(
    api: TestClient, db: Session, workspace: Workspace
):
    employee = make_member(db, workspace, MembershipRole.employee)
    asset = assigned_asset(db, workspace, employee)
    db.add(WorkspaceInvite(workspace_id=workspace.id, email="new@acme.com",
                           role=MembershipRole.employee, invited_by=employee.id))
    db.flush()
    asset_id = asset.id

    assert api.delete(f"/workspaces/{workspace.id}").status_code == 204

    assert not workspace_exists(db, workspace.id)
    assert db.get(Asset, asset_id) is None
    assert membership_of(db, workspace, employee) is None
    assert db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.workspace_id == workspace.id)) is None
    # The people themselves are untouched; they just lose this organization.
    assert db.get(User, employee.id) is not None


@pytest.mark.parametrize("role", [MembershipRole.admin, MembershipRole.employee])
def test_only_the_owner_deletes_the_organization(
    api: TestClient, db: Session, workspace: Workspace, role: MembershipRole
):
    act_as(make_member(db, workspace, role))
    assert api.delete(f"/workspaces/{workspace.id}").status_code == 403
    assert workspace_exists(db, workspace.id)


def test_nobody_deletes_a_personal_workspace(api: TestClient, db: Session, personal_workspace: Workspace, user: User):
    db.add(Membership(user_id=user.id, workspace_id=personal_workspace.id, role=MembershipRole.owner))
    db.flush()
    assert api.delete(f"/workspaces/{personal_workspace.id}").status_code == 422
    assert workspace_exists(db, personal_workspace.id)


def test_deleting_someone_elses_organization_is_404(api: TestClient, db: Session, other_workspace: Workspace):
    assert api.delete(f"/workspaces/{other_workspace.id}").status_code == 404
    assert workspace_exists(db, other_workspace.id)


# --- delete your account ---------------------------------------------------------


def test_an_owner_must_delete_their_organizations_first(api: TestClient, db: Session, user: User):
    response = api.delete("/me")

    assert response.status_code == 409
    assert "Test Workspace" in response.json()["detail"]
    db.expire_all()
    assert db.get(User, user.id) is not None


def test_deleting_your_account_removes_your_data_and_frees_the_email(
    api: TestClient, db: Session, workspace: Workspace, personal_workspace: Workspace
):
    person = make_member(db, workspace, MembershipRole.admin)
    db.add(Membership(user_id=person.id, workspace_id=personal_workspace.id, role=MembershipRole.owner))
    private = assigned_asset(db, personal_workspace, person)
    shared = assigned_asset(db, workspace, person)
    # An invite they sent, and one waiting for their email elsewhere.
    db.add(WorkspaceInvite(workspace_id=workspace.id, email="friend@acme.com",
                           role=MembershipRole.employee, invited_by=person.id))
    db.flush()
    private_id, shared_id, email = private.id, shared.id, person.email
    act_as(person)

    assert api.delete("/me").status_code == 204

    assert db.get(User, person.id) is None
    assert not workspace_exists(db, personal_workspace.id)
    assert db.get(Asset, private_id) is None
    # The organization keeps its asset; it is just no longer assigned to anyone.
    assert workspace_exists(db, workspace.id)
    assert db.get(Asset, shared_id).assigned_to_user_id is None
    assert db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.invited_by == person.id)) is None
    # The same email can sign up again: nothing still holds it.
    assert db.scalar(select(User).where(User.email == email)) is None
