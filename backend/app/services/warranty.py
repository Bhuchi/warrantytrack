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
"""

from __future__ import annotations

import enum
from datetime import date
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


def compute_status(
    end_date: date | None, today: date | None = None
) -> WarrantyStatus:
    """Status for one warranty end date. Pure — no DB, trivially unit-testable.

    `today` is injectable so tests can pin the clock; callers pass nothing in
    production. Boundaries: end_date == today is NOT past, so it is
    `expiring_soon`, not `expired`; exactly 30 days out is still `expiring_soon`.
    """
    if end_date is None:
        return WarrantyStatus.unknown

    today = today or date.today()
    days_left = (end_date - today).days

    if days_left < 0:
        return WarrantyStatus.expired
    if days_left <= EXPIRING_SOON_DAYS:
        return WarrantyStatus.expiring_soon
    return WarrantyStatus.active


def status_for_asset(asset: "Asset", today: date | None = None) -> WarrantyStatus:
    """Convenience: read the end_date off an Asset's warranty relationship.

    An asset with no warranty row is `unknown`. Callers that already hold the
    end_date should use compute_status() directly.
    """
    warranty = getattr(asset, "warranty", None)
    return compute_status(warranty.end_date if warranty else None, today)
