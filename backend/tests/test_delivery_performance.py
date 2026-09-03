from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.delivery_performance import eta_basis, summarize_delivery_performance
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


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


def test_delivery_performance_route_is_admin_only_and_factual() -> None:
    admin = client.post("/api/v1/auth/verify-otp", json={"phone": "+919000000001", "otp": "123456"}).json()["access_token"]
    customer = client.post("/api/v1/auth/verify-otp", json={"phone": "+919777777777", "otp": "123456"}).json()["access_token"]
    headers = lambda token: {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/admin/delivery-performance", headers=headers(customer)).status_code == 403
    response = client.get("/api/v1/admin/delivery-performance?window_days=30", headers=headers(admin))
    assert response.status_code == 200
    payload = response.json()
    assert payload["basis"] == "recorded_delivery_timestamps"
    assert "confidence" not in payload
    assert payload["delivered"] <= payload["total_records"]
