"""Business/query logic for notifications.

Routes stay thin: they resolve *who* (workspace + user from deps) and hand off
here. All SQL lives in services, so logic is testable without HTTP and reusable
(e.g. the scheduled scan can call the same module).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.services import notification_settings

#: The alerts the In-app switch controls. Other kinds (an asset assigned to
#: you) are not warranty reminders and always show.
WARRANTY_TYPES = (NotificationType.warranty_expiring, NotificationType.warranty_expired)


def list_for_workspace_user(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[int, list[Notification]]:
    """Return (unread_count, items) for one user in one workspace, newest first.

    Scoped by BOTH workspace_id AND user_id: a notification is per-person (see
    the model docstring), and this ordering matches the
    `ix_notifications_workspace_user_created` index, so the DB uses it directly.

    The bell list is small and bounded, so we count unread in Python off the
    rows we already loaded rather than firing a second COUNT query. If this ever
    needs to page, split it into a COUNT + a LIMIT query instead.
    """
    query = select(Notification).where(
        Notification.workspace_id == workspace_id,
        Notification.user_id == user_id,
    )
    # In-app off: the scan still writes the rows (they are its de-duplication
    # record) but the bell list and its badge leave the warranty ones out.
    if not notification_settings.for_user(db, user_id).in_app_enabled:
        query = query.where(Notification.type.not_in(WARRANTY_TYPES))
    items = db.scalars(query.order_by(Notification.created_at.desc())).all()

    unread = sum(1 for n in items if not n.read)
    return unread, list(items)


def mark_all_read(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    """Mark every unread notification for this user read. Returns rows changed.

    One bulk UPDATE instead of loading rows and looping in Python — the DB does
    it in a single statement and we never pull data we don't need. The
    `read == False` filter keeps it idempotent (running it twice changes nothing
    the second time) and avoids rewriting read_at on rows already read.
    """
    result = db.execute(
        update(Notification)
        .where(
            Notification.workspace_id == workspace_id,
            Notification.user_id == user_id,
            Notification.read.is_(False),
        )
        .values(read=True, read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return result.rowcount
