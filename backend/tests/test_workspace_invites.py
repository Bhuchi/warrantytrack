"""Pending organization invites, membership checks, and accept/decline flow."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_workspace
from app.main import app
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceType
from app.models.workspace_invite import WorkspaceInvite


def _invite(api: TestClient, workspace: Workspace, email: str = "New@Example.com", role: str = "employee"):
    return api.post(f"/workspaces/{workspace.id}/members", json={"email": email, "role": role})


def test_invite_appears_by_email_then_accepts(api: TestClient, db: Session, workspace: Workspace):
    response = _invite(api, workspace)
    assert response.status_code == 201, response.text
    assert response.json()["email"] == "new@example.com"
    assert response.json()["user_id"] is None
    assert response.json()["status"] == "invited"

    members = api.get(f"/workspaces/{workspace.id}/members")
    assert members.status_code == 200
    assert [row["status"] for row in members.json()] == ["active", "invited"]

    invited = User(cognito_sub="invitee", email="NEW@example.com", display_name="New Person")
    db.add(invited)
    db.flush()
    app.dependency_overrides[get_current_user] = lambda: invited.id

    me = api.get("/me").json()
    assert me["memberships"] == []
    assert me["invites"][0]["workspace"]["id"] == str(workspace.id)
    assert me["invites"][0]["invited_by"] == "Test User"

    accepted = api.post(f"/workspaces/{workspace.id}/invite/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "employee"
    assert accepted.json()["workspace"]["id"] == str(workspace.id)
    assert api.get("/me").json()["invites"] == []
    assert api.get("/me").json()["memberships"][0]["role"] == "employee"
    assert api.post(f"/workspaces/{workspace.id}/invite/accept").status_code == 404
    assert db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.workspace_id == workspace.id)) is None


def test_decline_removes_invite_and_allows_reinviting(
    api: TestClient, db: Session, workspace: Workspace, user: User,
):
    assert _invite(api, workspace).status_code == 201
    invited = User(cognito_sub="decliner", email="new@example.com")
    db.add(invited)
    db.flush()
    app.dependency_overrides[get_current_user] = lambda: invited.id
    assert api.post(f"/workspaces/{workspace.id}/invite/decline").status_code == 204
    assert api.get("/me").json()["invites"] == []
    assert api.post(f"/workspaces/{workspace.id}/invite/decline").status_code == 404
    app.dependency_overrides[get_current_user] = lambda: user.id
    assert _invite(api, workspace).status_code == 201


def test_invite_validates_role_email_workspace_and_duplicates(
    api: TestClient, db: Session, workspace: Workspace, user: User,
    personal_workspace: Workspace,
):
    assert _invite(api, workspace, "bad-email").status_code == 422
    assert _invite(api, workspace, role="owner").status_code == 422
    assert _invite(api, workspace, user.email.upper()).status_code == 409
    assert _invite(api, workspace).status_code == 201
    assert _invite(api, workspace, "NEW@EXAMPLE.COM").status_code == 409

    db.add(Membership(user_id=user.id, workspace_id=personal_workspace.id, role=MembershipRole.owner))
    db.flush()
    app.dependency_overrides[get_current_workspace] = lambda: personal_workspace.id
    assert _invite(api, personal_workspace).status_code == 422
    assert api.get(f"/workspaces/{workspace.id}/members").status_code == 404


def test_employee_cannot_manage_and_stranger_cannot_accept(
    api: TestClient, db: Session, workspace: Workspace, membership: Membership,
):
    assert _invite(api, workspace).status_code == 201
    membership.role = MembershipRole.employee
    db.flush()
    assert api.get(f"/workspaces/{workspace.id}/members").status_code == 403
    assert _invite(api, workspace, "another@example.com").status_code == 403
    assert api.post(f"/workspaces/{workspace.id}/invite/accept").status_code == 404
    assert api.post(f"/workspaces/{workspace.id}/invite/decline").status_code == 404

    foreign = Workspace(name="Foreign", type=WorkspaceType.organization)
    db.add(foreign)
    db.flush()
    assert api.get(f"/workspaces/{foreign.id}/members").status_code == 404


def test_admin_can_invite_and_list_members(
    api: TestClient, db: Session, workspace: Workspace, membership: Membership,
):
    membership.role = MembershipRole.admin
    db.flush()
    assert _invite(api, workspace, "teammate@example.com", "admin").status_code == 201
    listed = api.get(f"/workspaces/{workspace.id}/members")
    assert listed.status_code == 200
    assert listed.json()[0]["role"] == "admin"
    assert listed.json()[1]["email"] == "teammate@example.com"
