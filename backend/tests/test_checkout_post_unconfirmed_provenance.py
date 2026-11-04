"""POST checkout must reject unconfirmed pins without consuming stock or cart.

Uses synthetic PostgreSQL/PostGIS fixtures; no payment-provider calls.
"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token
from app.main import app
from app.models.orders import Cart, CartItem, Order
from app.models.commerce import StoreProduct
from tests import factories

client = TestClient(app)


@pytest.mark.parametrize("source", ["gps", "map_pin", "searched_place"])
@pytest.mark.parametrize("payment_method", ["cod", "upi"])
def test_checkout_rejects_unconfirmed_location_without_side_effects(
    source, payment_method,
):
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        store.opens_at = None
        store.closes_at = None
        village = db.get(factories.Village, store.village_id)
        address = factories.make_address(db, customer, village)
        # Exactly at the configured hub: only missing confirmation can reject.
        address.latitude = village.latitude
        address.longitude = village.longitude
        address.location_source = source
        address.location_confirmed_at = None
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
        listing_id, cart_id, store_id = listing.id, cart.id, store.id

    response = client.post(
        "/api/v1/orders/checkout",
        json={"address_id": str(address_id), "payment_method": payment_method},
        headers={
            "Authorization": f"Bearer {create_access_token(str(customer_id))}",
            "Idempotency-Key": f"reject-unconfirmed-{source}-{payment_method}",
        },
    )
    assert response.status_code == 409, response.text
    assert "Confirm your delivery location" in response.json()["detail"]

    with factories.session() as db:
        assert db.scalar(
            select(Order.id).where(
                Order.user_id == customer_id, Order.store_id == store_id,
            )
        ) is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 8
        assert db.get(Cart, cart_id).store_id == store_id
        assert db.scalar(
            select(CartItem.id).where(CartItem.cart_id == cart_id)
        ) is not None
