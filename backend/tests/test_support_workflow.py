from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _token(phone: str, name: str = "Support User") -> str:
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "123456", "full_name": name})
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_ticket_is_private_triaged_and_admin_resolved() -> None:
    suffix = int(uuid4().hex[:8], 16) % 100_000_000
    owner = _token(f"+917{suffix:09d}")
    stranger = _token(f"+916{suffix:09d}", "Other User")
    admin = _token("+919000000001", "Admin")

    created = client.post(
        "/api/v1/support/tickets",
        headers=_auth(owner),
        json={"subject": "Refund help", "description": "My cancelled order refund is missing"},
    )
    assert created.status_code == 201, created.text
    ticket = created.json()
    assert ticket["category"] == "payment"
    assert ticket["priority"] == "high"
    assert [row["id"] for row in client.get("/api/v1/support/tickets/me", headers=_auth(owner)).json()] == [ticket["id"]]
    assert client.get("/api/v1/support/tickets/me", headers=_auth(stranger)).json() == []

    forbidden = client.get("/api/v1/admin/support/tickets", headers=_auth(owner))
    assert forbidden.status_code == 403
    queue = client.get("/api/v1/admin/support/tickets", headers=_auth(admin))
    assert any(row["id"] == ticket["id"] for row in queue.json())
    resolved = client.patch(
        f"/api/v1/admin/support/tickets/{ticket['id']}",
        headers=_auth(admin),
        json={"status": "resolved", "resolution_notes": "Provider status verified; customer contacted."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None
