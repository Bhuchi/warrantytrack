"""Profile and workspace creation; membership IDs drive switching."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.membership import Membership, MembershipRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceType
from app.schemas.workspace import CreatedWorkspace, MeView, MembershipView, UserView, WorkspaceCreate

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
    return MeView(
        user=UserView.model_validate(user),
        memberships=[MembershipView(workspace=m.workspace, role=m.role) for m in memberships],
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
