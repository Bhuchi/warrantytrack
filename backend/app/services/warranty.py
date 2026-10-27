"""Warranty status — the one rule every Leg B surface shares.

There is NO status column (see the Warranty model): status is a function of the
warranty's `end_date` and today, computed on read so it is never stale. The
dashboard, the asset list/detail, and the nightly SES job all call this — the
rule lives here and nowhere else.

Rules (docs/architecture.md):
    active         end_date is more than 30 days away
    expiring_soon  end_date is within the next 30 days (0..30; today counts)
    expired        end_date is in the past
    unknown        no warranty / no end_date

Two callers need that rule in different shapes. One asset at a time (asset
detail, OCR confirm) wants a value -> `compute_status()`. Counting a whole
workspace (the dashboard, the nightly scan) must not load every row into
Python just to count it -> `soon_cutoff()` hands SQL the same boundary date, so
the database counts while the rule stays defined here, once.
"""

from __future__ import annotations

import enum
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.asset import Asset

EXPIRING_SOON_DAYS = 30


class WarrantyStatus(str, enum.Enum):
    """Mirrors WarrantyStatus in frontend/src/types/index.ts."""

    active = "active"
    expiring_soon = "expiring_soon"
    expired = "expired"
    unknown = "unknown"


def soon_cutoff(today: date, days: int = EXPIRING_SOON_DAYS) -> date:
    """The last `end_date` that still counts as expiring soon.

    Hand this to a SQL query instead of re-deriving `today + 30 days` there:

        expired       -> end_date <  today
        expiring_soon -> end_date >= today AND end_date <= soon_cutoff(today)
        active        -> end_date >  soon_cutoff(today)

    `compute_status()` below is written in terms of this same function, so the
    two paths cannot drift apart. There is a test that walks the boundaries day
    by day to prove it (tests/test_warranty_status.py).
    """
    return today + timedelta(days=days)


def compute_status(
    end_date: date | None,
    today: date | None = None,
    days: int = EXPIRING_SOON_DAYS,
) -> WarrantyStatus:
    """Status for one warranty end date. Pure — no DB, trivially unit-testable.

    `today` is injectable so tests can pin the clock; callers pass nothing in
    production. Boundaries: end_date == today is NOT past, so it is
    `expiring_soon`, not `expired`; exactly 30 days out is still `expiring_soon`.

    `days` narrows the window for `GET /dashboard/expiring?days=N`, which would
    otherwise need a second copy of this rule.
    """
    if end_date is None:
        return WarrantyStatus.unknown

    today = today or date.today()

    if end_date < today:
        return WarrantyStatus.expired
    if end_date <= soon_cutoff(today, days):
        return WarrantyStatus.expiring_soon
    return WarrantyStatus.active


def status_for_asset(
    asset: "Asset", today: date | None = None, days: int = EXPIRING_SOON_DAYS
) -> WarrantyStatus:
    """Convenience: read the end_date off an Asset's warranty relationship.

    An asset with no warranty row is `unknown`. Callers that already hold the
    end_date should use compute_status() directly.
    """
    warranty = getattr(asset, "warranty", None)
    return compute_status(warranty.end_date if warranty else None, today, days)


def days_remaining(end_date: date | None, today: date | None = None) -> int | None:
    """Whole days until the cover lapses; negative once it has, None if unknown.

    The notification copy says "expires in 30 days" and the expiring table
    sorts by urgency, so both need the number itself, not just the bucket.
    """
    if end_date is None:
        return None
    today = today or date.today()
    return (end_date - today).days
