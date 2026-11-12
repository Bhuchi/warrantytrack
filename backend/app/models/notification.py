from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.asset import Asset


class NotificationType(str, enum.Enum):
    warranty_expiring = "warranty_expiring"
    warranty_expired = "warranty_expired"
    asset_assigned = "asset_assigned"


class Notification(Base):
    """One item in the bell menu (D09), addressed to one user.

    Written by the scheduled warranty scan, which also sends the SES e-mail;
    the frontend only ever reads this table. A fan-out of one event to five
    admins is five rows — `read` is per person, so it cannot be one row.

    `title` is denormalized on purpose: it is rendered as written, so an asset
    renamed or deleted later does not rewrite history in the bell menu. That
    is also why `asset_id` is SET NULL rather than CASCADE — the notification
    outlives the asset, it just stops being a link.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        # `GET /notifications` is always "this user, in this workspace, newest
        # first", and the unread badge counts the same rows.
        Index(
            "ix_notifications_workspace_user_created",
            "workspace_id",
            "user_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )

    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notification_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    read: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    asset: Mapped[Asset | None] = relationship()
