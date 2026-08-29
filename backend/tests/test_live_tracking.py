from datetime import datetime, timedelta, timezone
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


def test_customer_sees_only_active_assigned_rider_location() -> None:
    admin_token = token("+919000000001")
    merchant_token = token("+919000000003")
    customer_phone = phone(7)
    rider_phone = phone(6)
    stranger_phone = phone(5)
    customer_token = token(customer_phone, "Tracking Customer")
    rider_token = token(rider_phone, "Tracking Rider")
    stranger_token = token(stranger_phone, "Tracking Stranger")

    rider_me = client.get("/api/v1/users/me", headers=auth(rider_token))
    assert rider_me.status_code == 200
    promote = client.patch(
        f"/api/v1/admin/users/{rider_me.json()['id']}/role",
        headers=auth(admin_token),
        json={"role": "delivery", "is_active": True},
    )
    assert promote.status_code == 200, promote.text

    stores = client.get("/api/v1/stores").json()
    assert stores
    store = stores[0]
    listings = client.get(f"/api/v1/stores/{store['id']}/products").json()
    assert listings
    villages = client.get("/api/v1/villages").json()
    assert villages

    address = client.post(
        "/api/v1/addresses/me",
        headers=auth(customer_token),
        json={
            "village_id": villages[0]["id"],
            "label": "Home",
            "recipient_name": "Tracking Customer",
            "phone": customer_phone,
            "house_details": "House 10",
            "landmark": "Tracking Chowk",
            "directions": "Blue gate",
            "latitude": 18.5210,
            "longitude": 73.8570,
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
        transition = client.patch(
            f"/api/v1/merchant/orders/{order_id}/status",
            headers=auth(merchant_token),
            json={"status": status},
        )
        assert transition.status_code == 200, transition.text

    available = client.get("/api/v1/delivery/available", headers=auth(rider_token))
    assert available.status_code == 200, available.text
    delivery = next(item for item in available.json() if item["order_id"] == order_id)
    delivery_id = delivery["id"]

    claimed = client.post(f"/api/v1/delivery/{delivery_id}/claim", headers=auth(rider_token))
    assert claimed.status_code == 200, claimed.text

    tracking_before = client.get(f"/api/v1/orders/{order_id}/tracking", headers=auth(customer_token))
    assert tracking_before.status_code == 200, tracking_before.text
    assert tracking_before.json()["tracking_active"] is True
    assert tracking_before.json()["rider"] is None

    forbidden = client.get(f"/api/v1/orders/{order_id}/tracking", headers=auth(stranger_token))
    assert forbidden.status_code == 403

    first_recorded_at = datetime.now(timezone.utc)
    ping = client.post(
        f"/api/v1/delivery/{delivery_id}/location",
        headers=auth(rider_token),
        json={
            "latitude": 18.5208,
            "longitude": 73.8568,
            "accuracy_m": 8.5,
            "heading_deg": 135,
            "speed_mps": 4.2,
            "recorded_at": first_recorded_at.isoformat(),
        },
    )
    assert ping.status_code == 201, ping.text

    too_fast = client.post(
        f"/api/v1/delivery/{delivery_id}/location",
        headers=auth(rider_token),
        json={
            "latitude": 18.5209,
            "longitude": 73.8569,
            "accuracy_m": 8.0,
            "heading_deg": 136,
            "speed_mps": 4.3,
            "recorded_at": (first_recorded_at + timedelta(seconds=1)).isoformat(),
        },
    )
    assert too_fast.status_code == 429, too_fast.text

    tracking = client.get(f"/api/v1/orders/{order_id}/tracking", headers=auth(customer_token))
    assert tracking.status_code == 200, tracking.text
    payload = tracking.json()
    assert payload["tracking_active"] is True
    assert payload["rider"]["latitude"] == 18.5208
    assert payload["rider"]["longitude"] == 73.8568
    assert payload["rider_location_age_seconds"] >= 0
    assert payload["store"]["latitude"] is not None
    assert payload["customer"]["latitude"] == 18.5210

    picked_up = client.patch(
        f"/api/v1/delivery/{delivery_id}/status",
        headers=auth(rider_token),
        json={"status": "picked_up"},
    )
    assert picked_up.status_code == 200, picked_up.text
    delivered = client.patch(
        f"/api/v1/delivery/{delivery_id}/status",
        headers=auth(rider_token),
        json={"status": "delivered"},
    )
    assert delivered.status_code == 200, delivered.text

    tracking_after = client.get(f"/api/v1/orders/{order_id}/tracking", headers=auth(customer_token))
    assert tracking_after.status_code == 200, tracking_after.text
    assert tracking_after.json()["tracking_active"] is False
    assert tracking_after.json()["rider"] is None
