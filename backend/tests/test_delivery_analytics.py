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


def promote_rider(admin_token: str, rider_token: str) -> str:
    me = client.get("/api/v1/users/me", headers=auth(rider_token))
    assert me.status_code == 200, me.text
    rider_id = me.json()["id"]
    response = client.patch(
        f"/api/v1/admin/users/{rider_id}/role",
        headers=auth(admin_token),
        json={"role": "delivery", "is_active": True},
    )
    assert response.status_code == 200, response.text
    return rider_id


def create_ready_order(customer_token: str, customer_phone: str, merchant_token: str) -> str:
    village = client.get("/api/v1/villages").json()[0]
    address = client.post(
        "/api/v1/addresses/me",
        headers=auth(customer_token),
        json={
            "village_id": village["id"],
            "label": "Home",
            "recipient_name": "ETA Customer",
            "phone": customer_phone,
            "house_details": "ETA House",
            "landmark": "ETA Chowk",
            "latitude": village["latitude"],
            "longitude": village["longitude"],
            "is_default": True,
        },
    )
    assert address.status_code == 201, address.text

    mine = client.get("/api/v1/stores/mine", headers=auth(merchant_token))
    assert mine.status_code == 200, mine.text
    stores = mine.json()
    assert stores
    store = stores[0]
    listings = client.get(f"/api/v1/stores/{store['id']}/products").json()
    assert listings
    listing = listings[0]
    added = client.post(
        "/api/v1/cart/items",
        headers=auth(customer_token),
        json={"store_product_id": listing["id"], "quantity": 1},
    )
    assert added.status_code == 200, added.text
    checkout = client.post(
        "/api/v1/orders/checkout",
        headers={**auth(customer_token), "Idempotency-Key": f"eta-{uuid4()}"},
        json={"address_id": address.json()["id"], "payment_method": "cod"},
    )
    assert checkout.status_code == 201, checkout.text
    order_id = checkout.json()["id"]
    for next_status in ("accepted", "preparing", "ready"):
        transitioned = client.patch(
            f"/api/v1/merchant/orders/{order_id}/status",
            headers=auth(merchant_token),
            json={"status": next_status},
        )
        assert transitioned.status_code == 200, transitioned.text
    return order_id


def test_eta_authorization_and_admin_performance_contract() -> None:
    admin_token = token("+919000000001")
    merchant_token = token("+919000000003")
    village = client.get("/api/v1/villages").json()[0]

    rider_token = token(phone(4), "ETA Rider")
    promote_rider(admin_token, rider_token)
    presence = client.put(
        "/api/v1/delivery/presence",
        headers=auth(rider_token),
        json={
            "latitude": village["latitude"] + 0.001,
            "longitude": village["longitude"] + 0.001,
            "is_online": True,
        },
    )
    assert presence.status_code == 200, presence.text

    customer_phone = phone(7)
    customer_token = token(customer_phone, "ETA Customer")
    order_id = create_ready_order(customer_token, customer_phone, merchant_token)

    available = client.get("/api/v1/delivery/available", headers=auth(rider_token))
    assert available.status_code == 200, available.text
    delivery_id = next(item["id"] for item in available.json() if item["order_id"] == order_id)

    assigned = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/auto-assign",
        headers=auth(admin_token),
        json={"max_radius_km": 15, "allow_batch": False},
    )
    assert assigned.status_code == 200, assigned.text

    eta = client.get(f"/api/v1/orders/{order_id}/eta", headers=auth(customer_token))
    assert eta.status_code == 200, eta.text
    payload = eta.json()
    assert payload["delivery_id"] == delivery_id
    assert payload["delivery_status"] == "assigned"
    assert payload["phase"] == "assigned_to_pickup"
    assert payload["eta_minutes"] >= 1
    assert payload["remaining_distance_km"] >= 0
    assert payload["confidence"] in {"medium", "high"}
    assert "postgis_route_distance" in payload["basis"]

    other_customer = token(phone(8), "Other Customer")
    forbidden = client.get(f"/api/v1/orders/{order_id}/eta", headers=auth(other_customer))
    assert forbidden.status_code == 403, forbidden.text

    performance = client.get(
        "/api/v1/admin/delivery-performance",
        headers=auth(admin_token),
        params={"window_days": 30, "target_minutes": 90},
    )
    assert performance.status_code == 200, performance.text
    metrics = performance.json()
    assert metrics["window_days"] == 30
    assert metrics["target_minutes"] == 90
    assert metrics["total_deliveries"] >= 1
    assert 0 <= metrics["failure_rate"] <= 1

    offline = client.put(
        "/api/v1/delivery/presence",
        headers=auth(rider_token),
        json={
            "latitude": village["latitude"],
            "longitude": village["longitude"],
            "is_online": False,
        },
    )
    assert offline.status_code == 200, offline.text
