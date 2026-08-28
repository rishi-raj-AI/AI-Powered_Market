from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

client = TestClient(app)
OTP = "123456"
DEV_ADMIN_PHONE = "+919000000001"


def token(phone: str, name: str | None = None) -> str:
    payload = {"phone": phone, "otp": OTP}
    if name:
        payload["full_name"] = name
    response = client.post("/api/v1/auth/verify-otp", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def random_phone(prefix: str) -> str:
    suffix = int(uuid4().hex[:8], 16) % 10_000_000
    return f"+91{prefix}{suffix:07d}"


def test_super_admin_controls_admin_roles_and_is_protected():
    super_token = token(DEV_ADMIN_PHONE)

    db = SessionLocal()
    try:
        super_admin = db.scalar(select(User).where(User.phone == DEV_ADMIN_PHONE))
        assert super_admin is not None
        super_admin.is_super_admin = True
        db.commit()
        super_admin_id = str(super_admin.id)
    finally:
        db.close()

    normal_admin_phone = random_phone("81")
    normal_admin_token = token(normal_admin_phone, "Normal Admin Candidate")
    normal_admin_me = client.get("/api/v1/users/me", headers=auth(normal_admin_token))
    assert normal_admin_me.status_code == 200
    normal_admin_id = normal_admin_me.json()["id"]

    promoted = client.patch(
        f"/api/v1/admin/users/{normal_admin_id}/role",
        headers=auth(super_token),
        json={"role": "admin", "is_active": True},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "admin"
    assert promoted.json()["is_super_admin"] is False

    candidate_phone = random_phone("82")
    candidate_token = token(candidate_phone, "Rider Candidate")
    candidate_me = client.get("/api/v1/users/me", headers=auth(candidate_token))
    assert candidate_me.status_code == 200
    candidate_id = candidate_me.json()["id"]

    forbidden_admin_promotion = client.patch(
        f"/api/v1/admin/users/{candidate_id}/role",
        headers=auth(normal_admin_token),
        json={"role": "admin", "is_active": True},
    )
    assert forbidden_admin_promotion.status_code == 403

    allowed_rider_promotion = client.patch(
        f"/api/v1/admin/users/{candidate_id}/role",
        headers=auth(normal_admin_token),
        json={"role": "delivery", "is_active": True},
    )
    assert allowed_rider_promotion.status_code == 200, allowed_rider_promotion.text
    assert allowed_rider_promotion.json()["role"] == "delivery"

    protected_super_admin = client.patch(
        f"/api/v1/admin/users/{super_admin_id}/role",
        headers=auth(normal_admin_token),
        json={"role": "customer", "is_active": True},
    )
    assert protected_super_admin.status_code == 403

    users = client.get("/api/v1/admin/users", headers=auth(super_token))
    assert users.status_code == 200, users.text
    super_admin_row = next(user for user in users.json() if user["id"] == super_admin_id)
    assert super_admin_row["role"] == "admin"
    assert super_admin_row["is_super_admin"] is True
