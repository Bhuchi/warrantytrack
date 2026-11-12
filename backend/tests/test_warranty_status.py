"""Unit tests for warranty status — pure logic, no database needed.

This is the pattern for testing service logic that doesn't touch the DB: pin
`today`, call the function, assert the status. DB-backed endpoints need a
Postgres fixture (future work); pure functions like this don't.
"""

from datetime import date, timedelta

import pytest

from app.services.warranty import (
    EXPIRING_SOON_DAYS,
    WarrantyStatus,
    compute_status,
    soon_cutoff,
)

TODAY = date(2026, 10, 27)


def test_unknown_when_no_end_date():
    assert compute_status(None, TODAY) is WarrantyStatus.unknown


def test_expired_when_end_date_is_past():
    assert compute_status(TODAY - timedelta(days=1), TODAY) is WarrantyStatus.expired


def test_end_date_today_is_expiring_soon_not_expired():
    assert compute_status(TODAY, TODAY) is WarrantyStatus.expiring_soon


def test_expiring_soon_at_30_day_boundary():
    assert compute_status(TODAY + timedelta(days=30), TODAY) is WarrantyStatus.expiring_soon


def test_active_beyond_30_days():
    assert compute_status(TODAY + timedelta(days=31), TODAY) is WarrantyStatus.active


# --- the boundary the scan and the dashboard count with --------------------


def test_soon_cutoff_is_the_documented_window():
    assert soon_cutoff(TODAY) == TODAY + timedelta(days=EXPIRING_SOON_DAYS)


@pytest.mark.parametrize("offset_days", range(-5, 40))
def test_sql_boundaries_agree_with_compute_status(offset_days: int):
    """The anti-drift test, and the reason `soon_cutoff()` is public.

    A query picks rows with date comparisons instead of calling
    `compute_status()` per row. Those comparisons are spelled out here and
    checked against the function day by day across the boundaries, so changing
    one side alone fails here rather than making two screens disagree.
    """
    end_date = TODAY + timedelta(days=offset_days)
    cutoff = soon_cutoff(TODAY)

    if end_date < TODAY:
        from_sql = WarrantyStatus.expired
    elif end_date <= cutoff:
        from_sql = WarrantyStatus.expiring_soon
    else:
        from_sql = WarrantyStatus.active

    assert compute_status(end_date, TODAY) is from_sql
