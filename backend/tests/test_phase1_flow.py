import re
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def seeded_village() -> dict:
    """The seeded pilot village, by identity rather than listing position."""
    villages = client.get("/api/v1/villages").json()
    for village in villages:
        if village["name"] == "Pilot Village":
            return village
    assert villages, "no villages are seeded"
    return villages[0]


def seeded_store() -> dict:
    """The seeded pilot store, by slug rather than listing position."""
    stores = client.get("/api/v1/stores").json()
    for store in stores:
        if store["slug"] == "patil-kirana-pilot":
            return store
    assert stores, "no stores are seeded"
    return stores[0]

OTP = "123456"


def token_for(phone: str, full_name: str | None = None) -> str:
    payload = {"phone": phone, "otp": OTP}
    if full_name:
        payload["full_name"] = full_name
    response = client.post("/api/v1/auth/verify-otp", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _unique_test_identity() -> tuple[str, str, str, str]:
    suffix = uuid4().hex[:8]
    numeric = int(suffix, 16) % 1_000_000_000
    customer_phone = f"+919{numeric:09d}"
    merchant_phone = f"+918{numeric:09d}"
    return customer_phone, merchant_phone, suffix, f"phase-one-kirana-{suffix}"


def test_complete_marketplace_flow() -> None:
    customer_phone, merchant_phone, suffix, store_slug = _unique_test_identity()
    customer_name = f"Phase One Customer {suffix}"
    merchant_name = f"Phase One Merchant {suffix}"
    store_name = f"Phase One Kirana {suffix}"

    admin_token = token_for("+919000000001")
    delivery_token = token_for("+919000000002")
    customer_token = token_for(customer_phone, customer_name)
    merchant_token = token_for(merchant_phone, merchant_name)
    stranger_token = token_for(f"+917{int(suffix, 16) % 1_000_000_000:09d}", "Unauthorised event viewer")

    villages = client.get("/api/v1/villages")
    assert villages.status_code == 200
    assert villages.json()
    village_id = seeded_village()["id"]

    address = client.post(
        "/api/v1/addresses/me",
        headers=auth(customer_token),
        json={
            "village_id": village_id,
            "label": "Home",
            "recipient_name": customer_name,
            "phone": customer_phone,
            "house_details": "House 1",
            "landmark": "Near Gram Panchayat",
            "directions": "Main road",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "is_default": True,
        },
    )
    assert address.status_code == 201, address.text
    address_id = address.json()["id"]

    merchant = client.post(
        "/api/v1/merchants/apply",
        headers=auth(merchant_token),
        json={"business_name": store_name, "gstin": None},
    )
    assert merchant.status_code == 201, merchant.text
    merchant_id = merchant.json()["id"]

    approved = client.patch(
        f"/api/v1/merchants/{merchant_id}/approve",
        headers=auth(admin_token),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    service_areas = client.get("/api/v1/service-areas")
    assert service_areas.status_code == 200
    assert service_areas.json()
    service_area_id = service_areas.json()[0]["id"]

    store = client.post(
        "/api/v1/stores",
        headers=auth(merchant_token),
        json={
            "village_id": village_id,
            "service_area_id": service_area_id,
            "name": store_name,
            "slug": store_slug,
            "description": "Pilot local grocery store",
            "phone": merchant_phone,
            "landmark": "Village square",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "opens_at": "08:00:00",
            "closes_at": "21:00:00",
            "delivery_enabled": True,
            "pickup_enabled": True,
        },
    )
    assert store.status_code == 201, store.text
    store_id = store.json()["id"]

    products = client.get("/api/v1/products?q=Rice")
    assert products.status_code == 200
    assert products.json()
    product_id = products.json()[0]["id"]

    listing = client.post(
        f"/api/v1/stores/{store_id}/products",
        headers=auth(merchant_token),
        json={
            "product_id": product_id,
            "price": "55.00",
            "mrp": "60.00",
            "stock_quantity": 20,
            "is_available": True,
        },
    )
    assert listing.status_code == 201, listing.text
    store_product_id = listing.json()["id"]

    cart = client.post(
        "/api/v1/cart/items",
        headers=auth(customer_token),
        json={"store_product_id": store_product_id, "quantity": 2},
    )
    assert cart.status_code == 200, cart.text
    assert cart.json()["subtotal"] == "110.00"

    checkout = client.post(
        "/api/v1/orders/checkout",
        headers=auth(customer_token),
        json={"address_id": address_id, "payment_method": "cod"},
    )
    assert checkout.status_code == 201, checkout.text
    order_id = checkout.json()["id"]
    assert checkout.json()["status"] == "placed"
    assert checkout.json()["total"] == "130.00"

    for next_status in ("accepted", "preparing", "ready"):
        transition = client.patch(
            f"/api/v1/merchant/orders/{order_id}/status",
            headers=auth(merchant_token),
            json={"status": next_status},
        )
        assert transition.status_code == 200, transition.text
        assert transition.json()["status"] == next_status

    available = client.get("/api/v1/delivery/available", headers=auth(delivery_token))
    assert available.status_code == 200, available.text
    matching = [item for item in available.json() if item["order_id"] == order_id]
    assert matching
    delivery_id = matching[0]["id"]

    claimed = client.post(f"/api/v1/delivery/{delivery_id}/claim", headers=auth(delivery_token))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "assigned"

    after_claim = client.get(f"/api/v1/orders/{order_id}", headers=auth(customer_token))
    assert after_claim.status_code == 200, after_claim.text
    assert after_claim.json()["status"] == "ready"

    picked_up = client.patch(
        f"/api/v1/delivery/{delivery_id}/status",
        headers=auth(delivery_token),
        json={"status": "picked_up"},
    )
    assert picked_up.status_code == 200, picked_up.text
    assert picked_up.json()["status"] == "picked_up"

    after_pickup = client.get(f"/api/v1/orders/{order_id}", headers=auth(customer_token))
    assert after_pickup.status_code == 200, after_pickup.text
    assert after_pickup.json()["status"] == "out_for_delivery"

    blocked_direct_delivery = client.patch(
        f"/api/v1/delivery/{delivery_id}/status",
        headers=auth(delivery_token),
        json={"status": "delivered"},
    )
    assert blocked_direct_delivery.status_code == 422

    blocked_without_proof = client.post(
        f"/api/v1/delivery/{delivery_id}/complete",
        headers=auth(delivery_token),
    )
    assert blocked_without_proof.status_code == 409

    challenge = client.post(
        f"/api/v1/delivery/{delivery_id}/proof/challenge",
        headers=auth(delivery_token),
    )
    assert challenge.status_code == 200, challenge.text

    notifications = client.get("/api/v1/notifications/me", headers=auth(customer_token))
    assert notifications.status_code == 200, notifications.text
    otp_event = next(item for item in notifications.json() if item["event_type"] == "delivery.otp")
    delivery_otp = re.search(r"\b(\d{6})\b", otp_event["body"])
    assert delivery_otp is not None

    proof = client.post(
        f"/api/v1/delivery/{delivery_id}/proof",
        headers=auth(delivery_token),
        json={
            "otp": delivery_otp.group(1),
            "recipient_name": customer_name,
            "notes": "Handed to customer",
        },
    )
    assert proof.status_code == 200, proof.text
    assert proof.json()["verified_at"] is not None

    blocked_without_cod = client.post(
        f"/api/v1/delivery/{delivery_id}/complete",
        headers=auth(delivery_token),
    )
    assert blocked_without_cod.status_code == 409

    wrong_cod = client.post(
        f"/api/v1/delivery/{delivery_id}/cod-collection",
        headers=auth(delivery_token),
        json={"amount": "129.00"},
    )
    assert wrong_cod.status_code == 422

    cod = client.post(
        f"/api/v1/delivery/{delivery_id}/cod-collection",
        headers=auth(delivery_token),
        json={"amount": "130.00"},
    )
    assert cod.status_code == 200, cod.text
    assert cod.json()["amount"] == "130.00"
    assert cod.json()["order_id"] == order_id

    cod_retry = client.post(
        f"/api/v1/delivery/{delivery_id}/cod-collection",
        headers=auth(delivery_token),
        json={"amount": "130.00"},
    )
    assert cod_retry.status_code == 200, cod_retry.text
    assert cod_retry.json()["id"] == cod.json()["id"]

    delivered = client.post(
        f"/api/v1/delivery/{delivery_id}/complete",
        headers=auth(delivery_token),
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()["status"] == "delivered"

    orders = client.get("/api/v1/orders/me", headers=auth(customer_token))
    assert orders.status_code == 200, orders.text
    matching_orders = [item for item in orders.json() if item["id"] == order_id]
    assert matching_orders
    assert matching_orders[0]["status"] == "delivered"
    assert matching_orders[0]["payment_status"] == "paid"

    events = client.get(f"/api/v1/orders/{order_id}/events", headers=auth(customer_token))
    assert events.status_code == 200, events.text
    transitions = {(item["entity_type"], item["from_status"], item["to_status"]) for item in events.json()}
    assert ("order", "ready", "out_for_delivery") in transitions
    assert ("delivery", "assigned", "picked_up") in transitions
    assert ("delivery", "picked_up", "delivered") in transitions
    assert ("order", "out_for_delivery", "delivered") in transitions

    forbidden_events = client.get(f"/api/v1/orders/{order_id}/events", headers=auth(stranger_token))
    assert forbidden_events.status_code == 403
