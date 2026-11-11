"""Public profile and workspace contract shared with frontend/types/index.ts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.membership import MembershipRole
from app.models.workspace import WorkspaceType


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str | None


class WorkspaceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    type: WorkspaceType
    created_at: datetime


class MembershipView(BaseModel):
    workspace: WorkspaceView
    role: MembershipRole


class MeView(BaseModel):
    user: UserView
    memberships: list[MembershipView]


class WorkspaceCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    type: Literal["organization"]


class CreatedWorkspace(WorkspaceView):
    role: MembershipRole
