from concurrent.futures import ThreadPoolExecutor
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


def customer_phone(prefix: int = 7) -> str:
    return f"+91{prefix}{int(uuid4().hex[:8], 16) % 1_000_000_000:09d}"


def create_address(customer_token: str, phone: str) -> str:
    village = client.get("/api/v1/villages").json()[0]
    response = client.post(
        "/api/v1/addresses/me",
        headers=auth(customer_token),
        json={
            "village_id": village["id"],
            "label": "Home",
            "recipient_name": "Checkout Safety Customer",
            "phone": phone,
            "house_details": "Concurrency House",
            "landmark": "Safety Chowk",
            "latitude": village["latitude"],
            "longitude": village["longitude"],
            "is_default": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def seeded_listing() -> tuple[str, str, str]:
    merchant_token = token("+919000000003")
    stores = client.get("/api/v1/stores").json()
    assert stores
    store_id = stores[0]["id"]
    inventory = client.get(f"/api/v1/stores/{store_id}/inventory", headers=auth(merchant_token))
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()
    return merchant_token, store_id, inventory.json()[0]["id"]


def set_stock(merchant_token: str, store_id: str, listing_id: str, quantity: int) -> None:
    response = client.patch(
        f"/api/v1/stores/{store_id}/products/{listing_id}",
        headers=auth(merchant_token),
        json={"stock_quantity": quantity, "is_available": quantity > 0},
    )
    assert response.status_code == 200, response.text


def stock_quantity(merchant_token: str, store_id: str, listing_id: str) -> int:
    inventory = client.get(f"/api/v1/stores/{store_id}/inventory", headers=auth(merchant_token))
    assert inventory.status_code == 200, inventory.text
    return next(item["stock_quantity"] for item in inventory.json() if item["id"] == listing_id)


def test_checkout_idempotency_returns_original_order_and_decrements_once() -> None:
    merchant_token, store_id, listing_id = seeded_listing()
    set_stock(merchant_token, store_id, listing_id, 5)

    phone = customer_phone()
    customer_token = token(phone, "Idempotent Customer")
    address_id = create_address(customer_token, phone)
    added = client.post(
        "/api/v1/cart/items",
        headers=auth(customer_token),
        json={"store_product_id": listing_id, "quantity": 1},
    )
    assert added.status_code == 200, added.text

    key = f"checkout-{uuid4()}"
    headers = {**auth(customer_token), "Idempotency-Key": key}
    first = client.post(
        "/api/v1/orders/checkout",
        headers=headers,
        json={"address_id": address_id, "payment_method": "cod"},
    )
    assert first.status_code == 201, first.text

    retry = client.post(
        "/api/v1/orders/checkout",
        headers=headers,
        json={"address_id": address_id, "payment_method": "cod"},
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first.json()["id"]
    assert retry.json()["order_number"] == first.json()["order_number"]
    assert stock_quantity(merchant_token, store_id, listing_id) == 4

    orders = client.get("/api/v1/orders/me", headers=auth(customer_token))
    assert orders.status_code == 200, orders.text
    matching = [item for item in orders.json() if item["id"] == first.json()["id"]]
    assert len(matching) == 1

    set_stock(merchant_token, store_id, listing_id, 20)


def test_concurrent_duplicate_checkout_returns_one_order_and_decrements_once() -> None:
    merchant_token, store_id, listing_id = seeded_listing()
    set_stock(merchant_token, store_id, listing_id, 5)

    phone = customer_phone(5)
    customer_token = token(phone, "Concurrent Idempotent Customer")
    address_id = create_address(customer_token, phone)
    added = client.post(
        "/api/v1/cart/items",
        headers=auth(customer_token),
        json={"store_product_id": listing_id, "quantity": 1},
    )
    assert added.status_code == 200, added.text

    key = f"duplicate-race-{uuid4()}"

    def do_checkout(_: int):
        return client.post(
            "/api/v1/orders/checkout",
            headers={**auth(customer_token), "Idempotency-Key": key},
            json={"address_id": address_id, "payment_method": "cod"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(do_checkout, range(2)))

    assert [response.status_code for response in responses] == [201, 201], [response.text for response in responses]
    order_ids = {response.json()["id"] for response in responses}
    order_numbers = {response.json()["order_number"] for response in responses}
    assert len(order_ids) == 1
    assert len(order_numbers) == 1
    assert stock_quantity(merchant_token, store_id, listing_id) == 4

    orders = client.get("/api/v1/orders/me", headers=auth(customer_token))
    assert orders.status_code == 200, orders.text
    matching = [item for item in orders.json() if item["id"] in order_ids]
    assert len(matching) == 1

    set_stock(merchant_token, store_id, listing_id, 20)


def test_concurrent_checkout_cannot_oversell_last_unit() -> None:
    merchant_token, store_id, listing_id = seeded_listing()
    set_stock(merchant_token, store_id, listing_id, 1)

    customers: list[tuple[str, str, str]] = []
    for prefix in (7, 8):
        phone = customer_phone(prefix)
        customer_token = token(phone, f"Concurrent Customer {prefix}")
        address_id = create_address(customer_token, phone)
        added = client.post(
            "/api/v1/cart/items",
            headers=auth(customer_token),
            json={"store_product_id": listing_id, "quantity": 1},
        )
        assert added.status_code == 200, added.text
        customers.append((customer_token, address_id, f"race-{uuid4()}"))

    def do_checkout(args: tuple[str, str, str]):
        customer_token, address_id, key = args
        return client.post(
            "/api/v1/orders/checkout",
            headers={**auth(customer_token), "Idempotency-Key": key},
            json={"address_id": address_id, "payment_method": "cod"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(do_checkout, customers))

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 409], [response.text for response in responses]
    assert stock_quantity(merchant_token, store_id, listing_id) == 0

    successful_orders = [response.json()["id"] for response in responses if response.status_code == 201]
    assert len(successful_orders) == 1

    set_stock(merchant_token, store_id, listing_id, 20)


def test_cancellation_restores_stock_exactly_once() -> None:
    merchant_token, store_id, listing_id = seeded_listing()
    set_stock(merchant_token, store_id, listing_id, 3)

    phone = customer_phone(6)
    customer_token = token(phone, "Cancellation Safety Customer")
    address_id = create_address(customer_token, phone)
    added = client.post(
        "/api/v1/cart/items",
        headers=auth(customer_token),
        json={"store_product_id": listing_id, "quantity": 1},
    )
    assert added.status_code == 200, added.text

    checkout = client.post(
        "/api/v1/orders/checkout",
        headers={**auth(customer_token), "Idempotency-Key": f"cancel-{uuid4()}"},
        json={"address_id": address_id, "payment_method": "cod"},
    )
    assert checkout.status_code == 201, checkout.text
    order_id = checkout.json()["id"]
    assert stock_quantity(merchant_token, store_id, listing_id) == 2

    first_cancel = client.post(f"/api/v1/orders/{order_id}/cancel", headers=auth(customer_token))
    assert first_cancel.status_code == 200, first_cancel.text
    assert first_cancel.json()["status"] == "cancelled"
    assert stock_quantity(merchant_token, store_id, listing_id) == 3

    retry_cancel = client.post(f"/api/v1/orders/{order_id}/cancel", headers=auth(customer_token))
    assert retry_cancel.status_code == 409, retry_cancel.text
    assert stock_quantity(merchant_token, store_id, listing_id) == 3

    set_stock(merchant_token, store_id, listing_id, 20)
