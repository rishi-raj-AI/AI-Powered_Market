from datetime import datetime, timezone

from app.api.v1.routes.delivery_windows import _ceil_half_hour, _generate_windows


def test_ceil_half_hour_rounds_forward():
    value = datetime(2026, 8, 30, 10, 37, tzinfo=timezone.utc)
    assert _ceil_half_hour(value) == datetime(2026, 8, 30, 11, 0, tzinfo=timezone.utc)


def test_generate_windows_returns_future_daytime_slots():
    now = datetime(2026, 8, 30, 8, 0, tzinfo=timezone.utc)
    slots = _generate_windows(now, days=1)
    assert slots
    assert all(start > now for start, _ in slots)
    assert all(7 <= start.hour < 21 for start, _ in slots)
