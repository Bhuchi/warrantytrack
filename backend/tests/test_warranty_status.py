"""Unit tests for warranty status — pure logic, no database needed.

This is the pattern for testing service logic that doesn't touch the DB: pin
`today`, call the function, assert the status. DB-backed endpoints need a
Postgres fixture (future work); pure functions like this don't.
"""

from datetime import date, timedelta

from app.services.warranty import WarrantyStatus, compute_status

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
