"""The signed-in person's notification settings (GitHub #82).

Per person, not per workspace, so no X-Workspace-Id: only `get_current_user`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.notification_settings import NotificationSettingsBody
from app.services import notification_settings as settings_service

router = APIRouter(tags=["notifications"])


def _body(settings: settings_service.Settings) -> NotificationSettingsBody:
    return NotificationSettingsBody(
        in_app_enabled=settings.in_app_enabled,
        email_enabled=settings.email_enabled,
        remind_days=list(settings.remind_days),
    )


@router.get("/me/notification-settings", response_model=NotificationSettingsBody)
def get_settings(
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationSettingsBody:
    """The saved settings, or the defaults if the person never saved any."""
    return _body(settings_service.for_user(db, user_id))


@router.put("/me/notification-settings", response_model=NotificationSettingsBody)
def put_settings(
    data: NotificationSettingsBody,
    user_id: uuid.UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationSettingsBody:
    """Replace all three settings. Bad reminder days are a 422 from the schema."""
    saved = settings_service.save(
        db,
        user_id,
        in_app_enabled=data.in_app_enabled,
        email_enabled=data.email_enabled,
        remind_days=data.remind_days,
    )
    return _body(saved)
