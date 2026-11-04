"""HTTP quote must reject unconfirmed coordinates even inside an assigned territory.

Synthetic PostgreSQL/PostGIS fixtures; no external provider calls or production data.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.orders import Cart, CartItem
from tests import factories

client = TestClient(app)


@pytest.mark.parametrize("source", ["gps", "map_pin", "searched_place"])
def test_cart_quote_rejects_unconfirmed_location_inside_territory(source):
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        store.opens_at = None
        store.closes_at = None
        village = db.get(factories.Village, store.village_id)
        address = factories.make_address(db, customer, village)
        # Coordinates are exactly at the configured hub; provenance alone blocks.
        address.latitude = village.latitude
        address.longitude = village.longitude
        address.location_source = source
        address.location_confirmed_at = None
        listing = factories.make_listing(db, store, price=Decimal("72.50"), stock=8)
        cart = Cart(user_id=customer.id, store_id=store.id)
        db.add(cart)
        db.flush()
        factories._track(cart)
        item = CartItem(cart_id=cart.id, store_product_id=listing.id, quantity=1)
        db.add(item)
        db.flush()
        factories._track(item)
        db.commit()
        customer_id, address_id = customer.id, address.id

    response = client.get(
        "/api/v1/cart/quote",
        params={"address_id": str(address_id)},
        headers={"Authorization": f"Bearer {create_access_token(str(customer_id))}"},
    )
    assert response.status_code == 200, response.text
    quote = response.json()
    assert quote["checkout_ready"] is False
    assert quote["serviceable"] is False
