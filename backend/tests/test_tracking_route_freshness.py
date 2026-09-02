from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.api.v1.routes.tracking import _location_is_fresh


def test_route_insight_requires_a_current_rider_fix() -> None:
    now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)

    assert _location_is_fresh(SimpleNamespace(recorded_at=now - timedelta(seconds=30)), now=now)
    assert not _location_is_fresh(SimpleNamespace(recorded_at=now - timedelta(seconds=31)), now=now)
    assert not _location_is_fresh(SimpleNamespace(recorded_at=now + timedelta(seconds=1)), now=now)
