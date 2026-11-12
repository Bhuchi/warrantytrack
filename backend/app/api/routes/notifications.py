"""Notifications routes (Leg B). Contract: docs/api.md -> Notifications."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_workspace
from app.db.session import get_db
from app.schemas.notification import NotificationList
from app.services import notification as notification_service

# No prefix here — main.py mounts this router at "/notifications", so the
# collection root is "".
router = APIRouter(tags=["notifications"])


@router.get("", response_model=NotificationList)
def list_notifications(
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
    user_id: uuid.UUID = Depends(get_current_user),
) -> NotificationList:
    """GET /notifications — the bell list for the current user (D09).

    FastAPI resolves the three Depends() first (a DB session, who the caller is),
    then runs this body. `response_model` validates the output against the
    contract, so a drift from NotificationList is a 500 here, not a silent bug in
    the frontend.
    """
    unread, items = notification_service.list_for_workspace_user(
        db, workspace_id, user_id
    )
    return NotificationList(unread=unread, items=items)


@router.post("/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    db: Session = Depends(get_db),
    workspace_id: uuid.UUID = Depends(get_current_workspace),
    user_id: uuid.UUID = Depends(get_current_user),
) -> None:
    """POST /notifications/mark-all-read — mark every unread as read.

    A write endpoint: it changes data, so the service commits. Returns 204 No
    Content (empty body) because the bell just clears its badge — it doesn't
    need anything back. That's why there is no response_model here.
    """
    notification_service.mark_all_read(db, workspace_id, user_id)
