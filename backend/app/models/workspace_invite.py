"""Pending organization invitations for email addresses without an account."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.membership import MembershipRole
from app.models.user import User
from app.models.workspace import Workspace


class WorkspaceInvite(Base):
    __tablename__ = "workspace_invites"
    __table_args__ = (
        Index("uq_workspace_invite_email", "workspace_id", "email", unique=True),
        Index("ix_workspace_invites_email", "email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[MembershipRole] = mapped_column(
        SAEnum(MembershipRole, name="membership_role"), nullable=False
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    workspace: Mapped[Workspace] = relationship()
    inviter: Mapped[User] = relationship()
