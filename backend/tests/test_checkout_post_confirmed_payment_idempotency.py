"""Confirmed in-territory checkout preserves payment state and idempotency.

Synthetic PostgreSQL/PostGIS only; never calls a payment provider.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.main import app
from app.models.commerce import StoreProduct
from app.models.orders import Cart, CartItem, Order, PaymentStatus
from tests import factories

client = TestClient(app)


@pytest.mark.parametrize("source", ["gps", "map_pin"])
@pytest.mark.parametrize("payment_method", ["cod", "upi"])
def test_confirmed_inside_checkout_payment_pending_and_idempotent_replay(
    source, payment_method,
):
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        store.opens_at = None
        store.closes_at = None
        village = db.get(factories.Village, store.village_id)
        address = factories.make_address(db, customer, village)
        address.latitude = village.latitude
        address.longitude = village.longitude
        address.location_source = source
        address.location_confirmed_at = datetime.now(timezone.utc)
        listing = factories.make_listing(
            db, store, price=Decimal("72.50"), stock=8,
        )
        cart = Cart(user_id=customer.id, store_id=store.id)
        db.add(cart)
        db.flush()
        factories._track(cart)
        item = CartItem(
            cart_id=cart.id, store_product_id=listing.id, quantity=1,
        )
        db.add(item)
        db.flush()
        factories._track(item)
        db.commit()
        customer_id, address_id = customer.id, address.id
        listing_id, cart_id = listing.id, cart.id

    headers = {
        "Authorization": f"Bearer {create_access_token(str(customer_id))}",
        "Idempotency-Key": f"confirmed-{source}-{payment_method}",
    }
    payload = {"address_id": str(address_id), "payment_method": payment_method}
    first = client.post("/api/v1/orders/checkout", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    order_id = first.json()["id"]

    with factories.session() as db:
        order = db.get(Order, order_id)
        assert order is not None
        assert order.payment_status == PaymentStatus.PENDING
        assert db.get(StoreProduct, listing_id).stock_quantity == 7
        assert db.get(Cart, cart_id).store_id is None
        assert db.scalar(
            select(func.count()).select_from(CartItem).where(CartItem.cart_id == cart_id)
        ) == 0

    replay = client.post("/api/v1/orders/checkout", json=payload, headers=headers)
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == order_id

    other_method = "upi" if payment_method == "cod" else "cod"
    conflict = client.post(
        "/api/v1/orders/checkout",
        json={"address_id": str(address_id), "payment_method": other_method},
        headers=headers,
    )
    assert conflict.status_code == 409, conflict.text

    with factories.session() as db:
        assert db.scalar(
            select(func.count()).select_from(Order).where(Order.user_id == customer_id)
        ) == 1
        assert db.get(StoreProduct, listing_id).stock_quantity == 7
        assert db.get(Order, order_id).payment_status == PaymentStatus.PENDING
