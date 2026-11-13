"""Read and save a person's notification settings (GitHub #82).

No row means the defaults. The scan and the bell list both read through
`for_user`, so "what does this person want" has one answer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.notification_settings import DEFAULT_REMIND_DAYS, NotificationSettings


@dataclass(frozen=True)
class Settings:
    in_app_enabled: bool = True
    email_enabled: bool = True
    remind_days: tuple[int, ...] = DEFAULT_REMIND_DAYS


DEFAULTS = Settings()


def _from_row(row: NotificationSettings) -> Settings:
    return Settings(
        in_app_enabled=row.in_app_enabled,
        email_enabled=row.email_enabled,
        remind_days=tuple(sorted(row.remind_days, reverse=True)),
    )


def for_user(db: Session, user_id: uuid.UUID) -> Settings:
    row = db.get(NotificationSettings, user_id)
    return _from_row(row) if row else DEFAULTS


def save(
    db: Session,
    user_id: uuid.UUID,
    *,
    in_app_enabled: bool,
    email_enabled: bool,
    remind_days: list[int],
) -> Settings:
    row = db.get(NotificationSettings, user_id)
    if row is None:
        row = NotificationSettings(user_id=user_id)
        db.add(row)
    row.in_app_enabled = in_app_enabled
    row.email_enabled = email_enabled
    row.remind_days = list(remind_days)
    db.commit()
    db.refresh(row)
    return _from_row(row)
