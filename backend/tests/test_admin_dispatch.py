from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
OTP = "123456"


def token(phone: str, name: str | None = None) -> str:
    payload = {"phone": phone, "otp": OTP}
    if name:
        payload["full_name"] = name
    response = client.post("/api/v1/auth/verify-otp", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def phone(prefix: int) -> str:
    return f"+91{prefix}{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"


def test_admin_can_assign_ready_delivery_to_active_rider() -> None:
    admin_token = token("+919000000001")
    merchant_token = token("+919000000003")
    customer_token = token(phone(7), "Dispatch Customer")
    rider_token = token(phone(6), "Dispatch Rider")

    rider = client.get("/api/v1/users/me", headers=auth(rider_token)).json()
    promote = client.patch(
        f"/api/v1/admin/users/{rider['id']}/role",
        headers=auth(admin_token),
        json={"role": "delivery", "is_active": True},
    )
    assert promote.status_code == 200, promote.text

    stores = client.get("/api/v1/stores").json()
    store = stores[0]
    listings = client.get(f"/api/v1/stores/{store['id']}/products").json()
    villages = client.get("/api/v1/villages").json()

    address = client.post(
        "/api/v1/addresses/me",
        headers=auth(customer_token),
        json={
            "village_id": villages[0]["id"],
            "label": "Home",
            "landmark": "Dispatch Chowk",
            "latitude": 20.081,
            "longitude": 73.791,
            "is_default": True,
        },
    )
    assert address.status_code == 201, address.text
    add = client.post(
        "/api/v1/cart/items",
        headers=auth(customer_token),
        json={"store_product_id": listings[0]["id"], "quantity": 1},
    )
    assert add.status_code == 200, add.text
    checkout = client.post(
        "/api/v1/orders/checkout",
        headers=auth(customer_token),
        json={"address_id": address.json()["id"], "payment_method": "cod"},
    )
    assert checkout.status_code == 201, checkout.text
    order_id = checkout.json()["id"]

    for status in ["accepted", "preparing", "ready"]:
        response = client.patch(
            f"/api/v1/merchant/orders/{order_id}/status",
            headers=auth(merchant_token),
            json={"status": status},
        )
        assert response.status_code == 200, response.text

    available = client.get("/api/v1/delivery/tasks/available", headers=auth(admin_token))
    assert available.status_code == 200, available.text
    task = next(item for item in available.json() if item["order_id"] == order_id)

    assigned = client.post(
        f"/api/v1/admin/deliveries/{task['id']}/assign",
        headers=auth(admin_token),
        json={"rider_id": rider["id"]},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["delivery_partner_id"] == rider["id"]
    assert assigned.json()["status"] == "assigned"

    rider_tasks = client.get("/api/v1/delivery/tasks/me", headers=auth(rider_token))
    assert rider_tasks.status_code == 200, rider_tasks.text
    assert any(item["order_id"] == order_id and item["status"] == "assigned" for item in rider_tasks.json())

    unavailable = client.get("/api/v1/delivery/tasks/available", headers=auth(admin_token))
    assert unavailable.status_code == 200
    assert all(item["order_id"] != order_id for item in unavailable.json())

    duplicate = client.post(
        f"/api/v1/admin/deliveries/{task['id']}/assign",
        headers=auth(admin_token),
        json={"rider_id": rider["id"]},
    )
    assert duplicate.status_code == 409
