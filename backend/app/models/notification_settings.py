from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: The reminder chips the Settings page offers, largest first.
REMIND_DAY_OPTIONS: tuple[int, ...] = (60, 30, 14, 7, 1)

#: What a person gets before they ever save anything. Keep in step with the
#: column default below and with DEFAULT_SETTINGS in the frontend.
DEFAULT_REMIND_DAYS: tuple[int, ...] = (30, 14, 7)


class NotificationSettings(Base):
    """One person's alert choices (Settings → Notifications, GitHub #82).

    Per person, not per workspace: alerts go to a person, and the same choices
    apply in every workspace they belong to. No row means the defaults, so a
    user who never opens the page needs nothing written for them.
    """

    __tablename__ = "notification_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    in_app_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    email_enabled: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    remind_days: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), server_default=text("'{30,14,7}'"), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )
