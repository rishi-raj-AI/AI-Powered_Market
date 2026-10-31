"""Pre-registration is auditable and does not bypass identity verification."""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.governance import AdministrativeAuditEvent
from app.models.user import User

client = TestClient(app)


def auth(phone: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "123456"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_onboarding_requires_capability_and_preserves_verification():
    admin = auth("+919000000001")
    stranger_phone = f"+918{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"
    stranger = auth(stranger_phone)
    new_phone = f"+917{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"
    payload = {"phone": new_phone, "full_name": "New Delivery Partner", "role": "delivery"}

    denied = client.post("/api/v1/admin/users/onboard", headers=stranger, json=payload)
    assert denied.status_code == 403, denied.text

    created = client.post("/api/v1/admin/users/onboard", headers=admin, json=payload)
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["role"] == "delivery"
    assert result["is_verified"] is False
    assert result["is_active"] is True

    duplicate = client.post("/api/v1/admin/users/onboard", headers=admin, json=payload)
    assert duplicate.status_code == 409, duplicate.text

    admin_candidate = dict(payload, phone=f"+916{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}", role="admin")
    forbidden = client.post("/api/v1/admin/users/onboard", headers=admin, json=admin_candidate)
    assert forbidden.status_code == 403, forbidden.text

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.phone == new_phone))
        assert user is not None
        assert user.is_verified is False
        audit = db.scalar(
            select(AdministrativeAuditEvent)
            .where(
                AdministrativeAuditEvent.action == "user.onboarded",
                AdministrativeAuditEvent.resource_id == str(user.id),
            )
        )
        assert audit is not None
        assert audit.resulting_state["is_verified"] is False
        assert audit.actor_user_id != user.id

    verified = client.post("/api/v1/auth/verify-otp", json={"phone": new_phone, "otp": "123456"})
    assert verified.status_code == 200, verified.text
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.phone == new_phone))
        assert user is not None
        assert user.is_verified is True
        assert user.role.value == "delivery"
