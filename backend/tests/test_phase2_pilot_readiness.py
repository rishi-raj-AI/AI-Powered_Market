from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
OTP = "123456"


def token_for(phone: str) -> str:
    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": phone, "otp": OTP},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_readiness_and_provider_configuration() -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200, ready.text
    assert ready.json()["database"] == "ok"
    assert ready.json()["redis"] == "ok"

    payments = client.get("/api/v1/payments/config")
    assert payments.status_code == 200
    assert payments.json()["provider"] == "razorpay"
    assert payments.json()["enabled"] is False

    notifications = client.get("/api/v1/notifications/config")
    assert notifications.status_code == 200
    assert notifications.json()["provider"] == "firebase"
    assert notifications.json()["enabled"] is False


def test_nearby_store_discovery_and_admin_overview() -> None:
    nearby = client.get(
        "/api/v1/stores/nearby",
        params={"lat": 18.5204, "lng": 73.8567, "radius_km": 2},
    )
    assert nearby.status_code == 200, nearby.text
    assert nearby.json()
    assert nearby.json()[0]["name"] == "Patil Kirana & Daily Needs"
    assert nearby.json()[0]["distance_km"] <= 0.1

    admin_token = token_for("+919000000001")
    overview = client.get("/api/v1/admin/overview", headers=auth(admin_token))
    assert overview.status_code == 200, overview.text
    data = overview.json()
    assert data["users"] >= 3
    assert data["active_stores"] >= 1
    assert data["merchants"]["approved"] >= 1
    assert "orders" in data
    assert "paid_gmv" in data


def test_notification_feed_requires_authentication() -> None:
    unauthenticated = client.get("/api/v1/notifications/me")
    assert unauthenticated.status_code in {401, 403}

    customer_token = token_for("+919000000020")
    authenticated = client.get("/api/v1/notifications/me", headers=auth(customer_token))
    assert authenticated.status_code == 200, authenticated.text
    assert isinstance(authenticated.json(), list)
