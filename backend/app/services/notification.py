"""Business/query logic for notifications.

Routes stay thin: they resolve *who* (workspace + user from deps) and hand off
here. All SQL lives in services, so logic is testable without HTTP and reusable
(e.g. the scheduled scan can call the same module).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification import Notification


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
    items = db.scalars(
        select(Notification)
        .where(
            Notification.workspace_id == workspace_id,
            Notification.user_id == user_id,
        )
        .order_by(Notification.created_at.desc())
    ).all()

    unread = sum(1 for n in items if not n.read)
    return unread, list(items)
