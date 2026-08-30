from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
OTP = "123456"


def token(phone: str) -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": OTP})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def test_support_triage_customer_and_admin_flow() -> None:
    customer = token("+919100000003")
    created = client.post(
        "/api/v1/support/tickets",
        headers=auth(customer),
        json={
            "subject": "Charged twice for payment",
            "description": "I was charged twice and need the duplicate payment reviewed immediately.",
        },
    )
    assert created.status_code == 201, created.text
    ticket = created.json()
    assert ticket["category"] == "payment"
    assert ticket["priority"] == "urgent"
    assert ticket["status"] == "open"
    assert ticket["suggested_action"]

    mine = client.get("/api/v1/support/tickets/me", headers=auth(customer))
    assert mine.status_code == 200, mine.text
    assert any(item["id"] == ticket["id"] for item in mine.json())

    forbidden = client.get("/api/v1/admin/support/tickets", headers=auth(customer))
    assert forbidden.status_code == 403, forbidden.text

    admin = token("+919000000001")
    queue = client.get(
        "/api/v1/admin/support/tickets",
        headers=auth(admin),
        params={"priority": "urgent"},
    )
    assert queue.status_code == 200, queue.text
    assert any(item["id"] == ticket["id"] for item in queue.json())

    resolved = client.patch(
        f"/api/v1/admin/support/tickets/{ticket['id']}",
        headers=auth(admin),
        json={"status": "resolved", "resolution_notes": "Duplicate charge reviewed by operations."},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None
