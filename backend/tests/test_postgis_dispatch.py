from concurrent.futures import ThreadPoolExecutor
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
    rider = client.get("/api/v1/users/me", headers=auth(rider_token))
    assert rider.status_code == 200, rider.text
    rider_id = rider.json()["id"]
    promoted = client.patch(
        f"/api/v1/admin/users/{rider_id}/role",
        headers=auth(admin_token),
        json={"role": "delivery", "is_active": True},
    )
    assert promoted.status_code == 200, promoted.text
    return rider_id


def set_presence(rider_token: str, latitude: float, longitude: float, online: bool = True) -> None:
    response = client.put(
        "/api/v1/delivery/presence",
        headers=auth(rider_token),
        json={"latitude": latitude, "longitude": longitude, "is_online": online},
    )
    assert response.status_code == 200, response.text


def create_ready_order(customer_token: str, customer_phone: str, merchant_token: str) -> tuple[str, str]:
    villages = client.get("/api/v1/villages").json()
    assert villages
    village = seeded_village()
    address = client.post(
        "/api/v1/addresses/me",
        headers=auth(customer_token),
        json={
            "village_id": village["id"],
            "label": "Home",
            "recipient_name": "Dispatch Customer",
            "phone": customer_phone,
            "house_details": "Dispatch House",
            "landmark": "Dispatch Chowk",
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
    store = seeded_store()
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
        headers={**auth(customer_token), "Idempotency-Key": f"dispatch-{uuid4()}"},
        json={"address_id": address.json()["id"], "payment_method": "cod"},
    )
    assert checkout.status_code == 201, checkout.text
    order_id = checkout.json()["id"]

    for next_status in ("accepted", "preparing", "ready"):
        transition = client.patch(
            f"/api/v1/merchant/orders/{order_id}/status",
            headers=auth(merchant_token),
            json={"status": next_status},
        )
        assert transition.status_code == 200, transition.text

    available = client.get("/api/v1/delivery/available", headers=auth(token("+919000000002")))
    assert available.status_code == 200, available.text
    delivery = next(item for item in available.json() if item["order_id"] == order_id)
    return order_id, delivery["id"]


def test_postgis_discovery_serviceability_and_nearest_dispatch() -> None:
    admin_token = token("+919000000001")
    merchant_token = token("+919000000003")
    villages = client.get("/api/v1/villages").json()
    assert villages
    village = seeded_village()

    serviceability = client.get(
        "/api/v1/location/serviceability",
        params={"latitude": village["latitude"], "longitude": village["longitude"]},
    )
    assert serviceability.status_code == 200, serviceability.text
    assert serviceability.json()["serviceable"] is True

    nearby = client.get(
        "/api/v1/stores/nearby",
        params={"lat": village["latitude"], "lng": village["longitude"], "radius_km": 20, "delivery": True},
    )
    assert nearby.status_code == 200, nearby.text
    assert nearby.json()
    assert nearby.json()[0]["distance_km"] >= 0

    near_token = token(phone(6), "Near Rider")
    far_token = token(phone(5), "Far Rider")
    near_id = promote_rider(admin_token, near_token)
    far_id = promote_rider(admin_token, far_token)
    set_presence(near_token, village["latitude"] + 0.001, village["longitude"] + 0.001)
    set_presence(far_token, village["latitude"] + 0.02, village["longitude"] + 0.02)

    customer_phone = phone(7)
    customer_token = token(customer_phone, "Dispatch Customer")
    _, delivery_id = create_ready_order(customer_token, customer_phone, merchant_token)

    assigned = client.post(
        f"/api/v1/admin/deliveries/{delivery_id}/auto-assign",
        headers=auth(admin_token),
        json={"max_radius_km": 15},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["rider_id"] == near_id
    assert assigned.json()["rider_id"] != far_id

    set_presence(far_token, village["latitude"] + 0.02, village["longitude"] + 0.02, online=False)
    second_phone = phone(8)
    second_token = token(second_phone, "No Rider Customer")
    _, second_delivery = create_ready_order(second_token, second_phone, merchant_token)
    unavailable = client.post(
        f"/api/v1/admin/deliveries/{second_delivery}/auto-assign",
        headers=auth(admin_token),
        json={"max_radius_km": 15},
    )
    assert unavailable.status_code == 409, unavailable.text
    assert unavailable.json()["detail"] == "No eligible delivery partner is currently available"

    set_presence(near_token, village["latitude"], village["longitude"], online=False)


def test_concurrent_dispatch_does_not_double_assign_one_rider() -> None:
    admin_token = token("+919000000001")
    merchant_token = token("+919000000003")
    village = seeded_village()

    rider_token = token(phone(4), "Race Rider")
    rider_id = promote_rider(admin_token, rider_token)
    set_presence(rider_token, village["latitude"] + 0.001, village["longitude"] + 0.001)

    deliveries: list[str] = []
    for prefix in (7, 8):
        customer_phone = phone(prefix)
        customer_token = token(customer_phone, f"Race Customer {prefix}")
        _, delivery_id = create_ready_order(customer_token, customer_phone, merchant_token)
        deliveries.append(delivery_id)

    def dispatch(delivery_id: str):
        return client.post(
            f"/api/v1/admin/deliveries/{delivery_id}/auto-assign",
            headers=auth(admin_token),
            json={"max_radius_km": 15},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(dispatch, deliveries))

    assert sorted(response.status_code for response in responses) == [200, 409], [response.text for response in responses]
    winner = next(response for response in responses if response.status_code == 200)
    assert winner.json()["rider_id"] == rider_id

    set_presence(rider_token, village["latitude"], village["longitude"], online=False)
