from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.delivery_performance import eta_basis, summarize_delivery_performance


def test_performance_uses_only_terminal_deliveries() -> None:
    now = datetime.now(timezone.utc)
    delivered = SimpleNamespace(assigned_at=now, picked_up_at=now + timedelta(minutes=5), delivered_at=now + timedelta(minutes=25))
    active = SimpleNamespace(assigned_at=now, picked_up_at=now + timedelta(minutes=4), delivered_at=None)
    result = summarize_delivery_performance([delivered, active])
    assert result.sample_count == 1
    assert result.median_assignment_to_pickup_seconds == 300
    assert result.median_pickup_to_delivery_seconds == 1200


def test_eta_prefers_live_route_and_never_invents_duration() -> None:
    assert eta_basis(route_duration_seconds=600, historical_delivery_seconds=900)["basis"] == "live_route"
    assert eta_basis(route_duration_seconds=None, historical_delivery_seconds=900)["basis"] == "historical_median"
    unavailable = eta_basis(route_duration_seconds=None, historical_delivery_seconds=None)
    assert unavailable == {"available": False, "duration_seconds": None, "basis": "unavailable"}
