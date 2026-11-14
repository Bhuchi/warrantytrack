"""GET / PUT /me/notification-settings (GitHub #82). Contract: docs/api.md."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.notification_settings import REMIND_DAY_OPTIONS


class NotificationSettingsBody(BaseModel):
    """The request and the response: all three fields, always."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    in_app_enabled: bool
    email_enabled: bool
    remind_days: list[int]

    @field_validator("remind_days")
    @classmethod
    def _known_days_largest_first(cls, days: list[int]) -> list[int]:
        unknown = sorted(set(days) - set(REMIND_DAY_OPTIONS))
        if unknown:
            raise ValueError(f"remind_days must come from {list(REMIND_DAY_OPTIONS)}; got {unknown}")
        if len(set(days)) != len(days):
            raise ValueError("remind_days must not repeat a value")
        # An empty list is allowed: no reminders before expiry, the "just
        # expired" alert still comes.
        return sorted(days, reverse=True)
