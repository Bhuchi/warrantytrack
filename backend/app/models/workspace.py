from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.membership import Membership


class WorkspaceType(str, enum.Enum):
    personal = "personal"
    organization = "organization"


class Workspace(Base):
    """A tenant boundary.

    A personal account is a workspace of type `personal` with exactly one
    member. Modelling it this way means every feature is written once instead
    of twice — see docs/architecture.md.
    """

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[WorkspaceType] = mapped_column(
        SAEnum(WorkspaceType, name="workspace_type"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
