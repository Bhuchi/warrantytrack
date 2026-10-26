"""Response shapes for the Notifications endpoints.

These mirror the `GET /notifications` contract in docs/api.md exactly — the
frontend bell menu (D09) is written against this shape, so the field names and
nesting here ARE the contract. Keep them in sync with api.md, not the other way
around.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationItem(BaseModel):
    """One row in the bell list (an element of `items[]`)."""

    # Lets Pydantic read straight off the SQLAlchemy object (n.id, n.type, ...)
    # instead of us building a dict by hand.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    read: bool
    asset_id: uuid.UUID | None
    title: str
    created_at: datetime


class NotificationList(BaseModel):
    """Envelope for GET /notifications: unread badge count + newest-first items."""

    unread: int
    items: list[NotificationItem]
