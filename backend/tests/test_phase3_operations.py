from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
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


def identity(prefix: int) -> str:
    return f"+91{prefix}{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"


def test_operational_controls_and_customer_cancellation() -> None:
    suffix = uuid4().hex[:8]
    admin_token = token_for("+919000000001")
    customer_phone = identity(7)
    merchant_phone = identity(8)
    customer_token = token_for(customer_phone, f"Ops Customer {suffix}")
    merchant_token = token_for(merchant_phone, f"Ops Merchant {suffix}")

    villages = client.get("/api/v1/villages").json()
    assert villages
    village_id = villages[0]["id"]
    service_areas = client.get("/api/v1/service-areas").json()
    service_area_id = service_areas[0]["id"] if service_areas else None

    application = client.post(
        "/api/v1/merchants/apply",
        headers=auth(merchant_token),
        json={"business_name": f"Ops Kirana {suffix}", "gstin": None},
    )
    assert application.status_code == 201, application.text
    merchant_id = application.json()["id"]

    activate = client.patch(
        f"/api/v1/merchants/{merchant_id}/status",
        headers=auth(admin_token),
        json={"status": "approved"},
    )
    assert activate.status_code == 200, activate.text

    store_payload = {
        "village_id": village_id,
        "service_area_id": service_area_id,
        "name": f"Operations Store {suffix}",
        "slug": f"operations-store-{suffix}",
        "description": "Operations regression storefront",
        "phone": merchant_phone,
        "landmark": "Near test chowk",
        "latitude": 20.08,
        "longitude": 73.79,
        "opens_at": "08:00:00",
        "closes_at": "21:00:00",
        "delivery_enabled": True,
        "pickup_enabled": True,
    }
    store = client.post("/api/v1/stores", headers=auth(merchant_token), json=store_payload)
    assert store.status_code == 201, store.text
    store_id = store.json()["id"]

    edited = client.patch(
        f"/api/v1/stores/{store_id}",
        headers=auth(merchant_token),
        json={"description": "Updated operations storefront", "closes_at": "22:00:00"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["description"] == "Updated operations storefront"

    products = client.get("/api/v1/products").json()
    assert products
    product_id = products[0]["id"]
    listing = client.post(
        f"/api/v1/stores/{store_id}/products",
        headers=auth(merchant_token),
        json={"product_id": product_id, "price": "49.00", "mrp": "55.00", "stock_quantity": 7, "is_available": True},
    )
    assert listing.status_code == 201, listing.text
    listing_id = listing.json()["id"]

    inventory = client.get(f"/api/v1/stores/{store_id}/inventory", headers=auth(merchant_token))
    assert inventory.status_code == 200, inventory.text
    assert any(item["id"] == listing_id for item in inventory.json())

    inventory_update = client.patch(
        f"/api/v1/stores/{store_id}/products/{listing_id}",
        headers=auth(merchant_token),
        json={"price": "47.00", "stock_quantity": 9, "is_available": False},
    )
    assert inventory_update.status_code == 200, inventory_update.text
    assert inventory_update.json()["price"] == "47.00"
    assert inventory_update.json()["stock_quantity"] == 9
    assert inventory_update.json()["is_available"] is False

    hidden_listing = client.get(f"/api/v1/stores/{store_id}/products")
    assert hidden_listing.status_code == 200, hidden_listing.text
    assert all(item["id"] != listing_id for item in hidden_listing.json())

    inventory_reopen = client.patch(
        f"/api/v1/stores/{store_id}/products/{listing_id}",
        headers=auth(merchant_token),
        json={"price": "49.00", "stock_quantity": 7, "is_available": True},
    )
    assert inventory_reopen.status_code == 200, inventory_reopen.text

    suspend = client.patch(
        f"/api/v1/merchants/{merchant_id}/status",
        headers=auth(admin_token),
        json={"status": "suspended"},
    )
    assert suspend.status_code == 200, suspend.text
    hidden = client.get(f"/api/v1/stores/{store_id}")
    assert hidden.status_code == 404

    reactivate = client.patch(
        f"/api/v1/merchants/{merchant_id}/status",
        headers=auth(admin_token),
        json={"status": "approved"},
    )
    assert reactivate.status_code == 200, reactivate.text
    visible = client.get(f"/api/v1/stores/{store_id}")
    assert visible.status_code == 200, visible.text

    address = client.post(
        "/api/v1/addresses/me",
        headers=auth(customer_token),
        json={
            "village_id": village_id,
            "label": "Home",
            "recipient_name": f"Ops Customer {suffix}",
            "phone": customer_phone,
            "house_details": "House 3",
            "landmark": "Near test temple",
            "directions": "Green gate",
            "latitude": 20.081,
            "longitude": 73.791,
            "is_default": True,
        },
    )
    assert address.status_code == 201, address.text
    address_id = address.json()["id"]

    first_add = client.post(
        "/api/v1/cart/items",
        headers=auth(customer_token),
        json={"store_product_id": listing_id, "quantity": 1},
    )
    assert first_add.status_code == 200, first_add.text
    cleared = client.delete("/api/v1/cart", headers=auth(customer_token))
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["items"] == []

    second_add = client.post(
        "/api/v1/cart/items",
        headers=auth(customer_token),
        json={"store_product_id": listing_id, "quantity": 2},
    )
    assert second_add.status_code == 200, second_add.text
    order = client.post(
        "/api/v1/orders/checkout",
        headers=auth(customer_token),
        json={"address_id": address_id, "payment_method": "cod"},
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    detail = client.get(f"/api/v1/orders/{order_id}", headers=auth(customer_token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["store_name"] == store_payload["name"]
    assert len(detail.json()["items"]) == 1
    assert detail.json()["delivery"]["status"] == "unassigned"

    stock_after_checkout = client.get(
        f"/api/v1/stores/{store_id}/inventory", headers=auth(merchant_token)
    ).json()[0]["stock_quantity"]
    assert stock_after_checkout == 5

    cancelled = client.post(f"/api/v1/orders/{order_id}/cancel", headers=auth(customer_token))
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    stock_after_cancel = client.get(
        f"/api/v1/stores/{store_id}/inventory", headers=auth(merchant_token)
    ).json()[0]["stock_quantity"]
    assert stock_after_cancel == 7

    overview = client.get("/api/v1/admin/overview", headers=auth(admin_token))
    assert overview.status_code == 200, overview.text
    payload = overview.json()
    assert "villages" in payload
    assert "gross_order_value" in payload
    assert "operations" in payload
    assert "suspended" in payload["merchants"]
