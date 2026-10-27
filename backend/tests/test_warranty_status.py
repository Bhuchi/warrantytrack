"""Unit tests for warranty status — pure logic, no database needed.

This is the pattern for testing service logic that doesn't touch the DB: pin
`today`, call the function, assert the status. DB-backed endpoints need a
Postgres fixture (see conftest.py); pure functions like this don't.
"""

from datetime import date, timedelta

import pytest

from app.services.warranty import (
    EXPIRING_SOON_DAYS,
    WarrantyStatus,
    compute_status,
    days_remaining,
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


@pytest.mark.parametrize(
    ("offset_days", "expected"),
    [
        (-365, WarrantyStatus.expired),
        (-1, WarrantyStatus.expired),
        (0, WarrantyStatus.expiring_soon),
        (1, WarrantyStatus.expiring_soon),
        (29, WarrantyStatus.expiring_soon),
        (30, WarrantyStatus.expiring_soon),
        (31, WarrantyStatus.active),
        (3650, WarrantyStatus.active),
    ],
)
def test_status_across_the_boundaries(offset_days: int, expected: WarrantyStatus):
    """The same five rules above, swept as a table so a boundary slip shows up."""
    assert compute_status(TODAY + timedelta(days=offset_days), TODAY) is expected


def test_window_is_configurable():
    """`GET /dashboard/expiring?days=N` narrows the window without a new rule."""
    seven_days_out = TODAY + timedelta(days=7)
    assert compute_status(seven_days_out, TODAY, days=30) is WarrantyStatus.expiring_soon
    assert compute_status(seven_days_out, TODAY, days=3) is WarrantyStatus.active


def test_soon_cutoff_is_the_documented_window():
    assert soon_cutoff(TODAY) == TODAY + timedelta(days=EXPIRING_SOON_DAYS)


@pytest.mark.parametrize("offset_days", range(-5, 40))
def test_sql_boundaries_agree_with_compute_status(offset_days: int):
    """The anti-drift test, and the reason `soon_cutoff()` is public.

    app/services/dashboard.py counts with SQL comparisons instead of loading
    every row:

        expired       -> end_date <  today
        expiring_soon -> end_date >= today AND end_date <= cutoff
        active        -> end_date >  cutoff

    Those comparisons are spelled out here in Python and checked against
    `compute_status()` day by day across the boundaries. Change one side only
    and this fails, instead of the dashboard quietly disagreeing with the asset
    detail screen.
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


@pytest.mark.parametrize(("offset_days", "expected"), [(-3, -3), (0, 0), (30, 30)])
def test_days_remaining(offset_days: int, expected: int):
    """Negative once lapsed — the notification copy needs the number itself."""
    assert days_remaining(TODAY + timedelta(days=offset_days), TODAY) == expected


def test_days_remaining_is_none_without_a_warranty():
    assert days_remaining(None, TODAY) is None
