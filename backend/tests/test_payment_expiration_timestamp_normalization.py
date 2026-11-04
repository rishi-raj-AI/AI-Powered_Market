"""Regression for legacy timestamp handling in unpaid UPI expiry."""
from datetime import datetime, timedelta, timezone

from app.services.payment_expiration import _utc_datetime


def test_expiration_normalizes_naive_database_utc_timestamp():
    naive = datetime(2026, 11, 5, 1, 2, 3)
    assert _utc_datetime(naive) == datetime(2026, 11, 5, 1, 2, 3, tzinfo=timezone.utc)


def test_expiration_normalizes_offset_aware_timestamp():
    ist = timezone(timedelta(hours=5, minutes=30))
    timestamp = datetime(2026, 11, 5, 6, 32, 3, tzinfo=ist)
    assert _utc_datetime(timestamp) == datetime(2026, 11, 5, 1, 2, 3, tzinfo=timezone.utc)


def test_expiration_cutoff_comparison_handles_naive_legacy_timestamp():
    cutoff = datetime(2026, 11, 5, 1, 2, 3, tzinfo=timezone.utc)
    assert _utc_datetime(datetime(2026, 11, 5, 1, 2, 2)) < cutoff
    assert _utc_datetime(datetime(2026, 11, 5, 1, 2, 4)) >= cutoff
