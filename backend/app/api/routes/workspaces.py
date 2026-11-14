"""Profile and workspace creation; membership IDs drive switching."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_membership, get_current_user
from app.db.session import get_db
from app.models.asset import Asset
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceType
from app.models.workspace_invite import WorkspaceInvite
from app.schemas.workspace import (
    CreatedWorkspace, InviteView, MeView, MembershipView, UserView,
    WorkspaceCreate, WorkspaceInviteCreate, WorkspaceMemberView,
)

router = APIRouter(tags=["workspaces"])


@router.get("/me", response_model=MeView)
def me(user_id: uuid.UUID = Depends(get_current_user), db: Session = Depends(get_db)) -> MeView:
    user = db.get(User, user_id)
    memberships = db.scalars(
        select(Membership).options(selectinload(Membership.workspace))
        .where(Membership.user_id == user_id)
    ).all()
    memberships.sort(key=lambda member: (
        member.workspace.type is not WorkspaceType.personal,
        member.workspace.name.lower(),
    ))
    invites = db.scalars(
        select(WorkspaceInvite)
        .options(selectinload(WorkspaceInvite.workspace), selectinload(WorkspaceInvite.inviter))
        .where(WorkspaceInvite.email == func.lower(user.email))
    ).all()
    return MeView(
        user=UserView.model_validate(user),
        memberships=[MembershipView(workspace=m.workspace, role=m.role) for m in memberships],
        invites=[InviteView(
            workspace=invite.workspace,
            role=invite.role,
            invited_by=invite.inviter.display_name or invite.inviter.email,
            invited_at=invite.created_at,
        ) for invite in invites],
    )


@router.post("/workspaces", response_model=CreatedWorkspace, status_code=status.HTTP_201_CREATED)
def create_workspace(
    data: WorkspaceCreate,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CreatedWorkspace:
    workspace = Workspace(name=data.name, type=WorkspaceType.organization)
    db.add(workspace)
    db.flush()
    db.add(Membership(user_id=user_id, workspace_id=workspace.id, role=MembershipRole.owner))
    db.commit()
    db.refresh(workspace)
    return CreatedWorkspace.model_validate({
        "id": workspace.id, "name": workspace.name, "type": workspace.type,
        "created_at": workspace.created_at, "role": MembershipRole.owner,
    })


def _manager_for_path(manager: Membership, workspace_id: uuid.UUID) -> None:
    if manager.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Not found")
    if manager.role is MembershipRole.employee:
        raise HTTPException(status_code=403, detail="Only an owner or admin can do this.")


@router.get("/workspaces/{id}/members", response_model=list[WorkspaceMemberView])
def list_members(
    id: uuid.UUID,
    manager: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> list[WorkspaceMemberView]:
    workspace_id = id
    _manager_for_path(manager, workspace_id)
    members = db.scalars(
        select(Membership).options(selectinload(Membership.user))
        .where(Membership.workspace_id == workspace_id)
    ).all()
    invites = db.scalars(select(WorkspaceInvite).where(WorkspaceInvite.workspace_id == workspace_id)).all()
    active = [WorkspaceMemberView(
        user_id=member.user_id, email=member.user.email,
        display_name=member.user.display_name, role=member.role,
        status="active", invited_at=None,
    ) for member in members]
    pending = [WorkspaceMemberView(
        user_id=None, email=invite.email, display_name=None,
        role=invite.role, status="invited", invited_at=invite.created_at,
    ) for invite in invites]
    return sorted(active, key=lambda row: row.email.lower()) + sorted(pending, key=lambda row: row.email)


@router.post(
    "/workspaces/{id}/members",
    response_model=WorkspaceMemberView,
    status_code=status.HTTP_201_CREATED,
)
def invite_member(
    id: uuid.UUID,
    data: WorkspaceInviteCreate,
    manager: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> WorkspaceMemberView:
    workspace_id = id
    _manager_for_path(manager, workspace_id)
    workspace = db.get(Workspace, workspace_id)
    if workspace.type is not WorkspaceType.organization:
        raise HTTPException(status_code=422, detail="Only organizations can invite members")

    email = data.email.lower()
    existing_member = db.scalar(
        select(Membership).join(User).where(
            Membership.workspace_id == workspace_id, func.lower(User.email) == email
        )
    )
    existing_invite = db.scalar(select(WorkspaceInvite).where(
        WorkspaceInvite.workspace_id == workspace_id, WorkspaceInvite.email == email
    ))
    if existing_member or existing_invite:
        raise HTTPException(status_code=409, detail="Already a member or invited")

    invite = WorkspaceInvite(
        workspace_id=workspace_id, email=email,
        role=MembershipRole(data.role), invited_by=manager.user_id,
    )
    db.add(invite)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Already invited") from None
    db.refresh(invite)
    return WorkspaceMemberView(
        user_id=None, email=invite.email, display_name=None,
        role=invite.role, status="invited", invited_at=invite.created_at,
    )


def _own_invite(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceInvite:
    user = db.get(User, user_id)
    invite = db.scalar(select(WorkspaceInvite).where(
        WorkspaceInvite.workspace_id == workspace_id,
        WorkspaceInvite.email == func.lower(user.email),
    ))
    if invite is None:
        raise HTTPException(status_code=404, detail="Not found")
    return invite


@router.post("/workspaces/{workspace_id}/invite/accept", response_model=MembershipView)
def accept_invite(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MembershipView:
    invite = _own_invite(db, workspace_id, user_id)
    if db.scalar(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == user_id
    )) is not None:
        raise HTTPException(status_code=404, detail="Not found")
    workspace = db.get(Workspace, workspace_id)
    role = invite.role
    db.add(Membership(workspace_id=workspace_id, user_id=user_id, role=role))
    db.delete(invite)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Not found") from None
    return MembershipView(workspace=workspace, role=role)


@router.post("/workspaces/{workspace_id}/invite/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_invite(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    invite = _own_invite(db, workspace_id, user_id)
    db.delete(invite)
    db.commit()


# --- undoing membership (GitHub #80) -----------------------------------------
#
# These read the caller's role in the workspace named by the path, not by the
# X-Workspace-Id header: leaving or tidying up a workspace should not depend on
# which one the browser happens to have selected. No membership there is 404,
# as everywhere else.


def _caller_in(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    membership = db.scalar(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == user_id
    ))
    if membership is None:
        raise HTTPException(status_code=404, detail="Not found")
    return membership


def _require_manager(membership: Membership) -> None:
    if membership.role is MembershipRole.employee:
        raise HTTPException(status_code=403, detail="Only an owner or admin can do this.")


def _unassign(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Assets assigned to someone who can no longer see them go back to nobody."""
    db.execute(
        update(Asset)
        .where(Asset.workspace_id == workspace_id, Asset.assigned_to_user_id == user_id)
        .values(assigned_to_user_id=None)
    )


@router.delete("/workspaces/{workspace_id}/invites", status_code=status.HTTP_204_NO_CONTENT)
def cancel_invite(
    workspace_id: uuid.UUID,
    email: str = Query(min_length=1, max_length=320),
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Cancel a pending invite. Owner or admin."""
    _require_manager(_caller_in(db, workspace_id, user_id))
    invite = db.scalar(select(WorkspaceInvite).where(
        WorkspaceInvite.workspace_id == workspace_id,
        WorkspaceInvite.email == email.strip().lower(),
    ))
    if invite is None:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(invite)
    db.commit()


@router.delete("/workspaces/{workspace_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: uuid.UUID,
    member_user_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove someone who has joined. Owner or admin; never the owner, never yourself."""
    _require_manager(_caller_in(db, workspace_id, user_id))
    target = db.scalar(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == member_user_id
    ))
    if target is None:
        raise HTTPException(status_code=404, detail="Not found")
    if target.role is MembershipRole.owner:
        raise HTTPException(status_code=409, detail="The owner can't be removed.")
    if member_user_id == user_id:
        raise HTTPException(status_code=409, detail="Use leave to remove yourself.")
    _unassign(db, workspace_id, member_user_id)
    db.delete(target)
    db.commit()


@router.post("/workspaces/{workspace_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_workspace(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """The caller leaves an organization. Admin or employee; the owner stays."""
    membership = _caller_in(db, workspace_id, user_id)
    if db.get(Workspace, workspace_id).type is WorkspaceType.personal:
        raise HTTPException(status_code=422, detail="You can't leave your personal workspace.")
    if membership.role is MembershipRole.owner:
        raise HTTPException(status_code=409, detail="The owner can't leave the organization.")
    _unassign(db, workspace_id, user_id)
    db.delete(membership)
    db.commit()
