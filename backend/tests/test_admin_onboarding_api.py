"""Pre-registration must reject callers without elevated role-management authority."""
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth(phone: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "123456"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_onboarding_requires_elevated_capability():
    normal_admin = auth("+919000000001")
    customer_phone = f"+918{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"
    customer = auth(customer_phone)
    new_phone = f"+917{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"
    payload = {"phone": new_phone, "full_name": "New Delivery Partner", "role": "delivery"}

    assert client.post("/api/v1/admin/users/onboard", headers=customer, json=payload).status_code == 403
    assert client.post("/api/v1/admin/users/onboard", headers=normal_admin, json=payload).status_code == 403
    assert client.post("/api/v1/admin/users/onboard", json=payload).status_code == 401
