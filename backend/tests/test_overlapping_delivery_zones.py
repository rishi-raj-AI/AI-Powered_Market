"""Regression: a closer hub with a smaller radius must not block a covering zone.

Uses the same real PostGIS database as Backend CI. No mocked geometry: this
reproduces the previous address-admission versus checkout disagreement.
"""
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes.checkout import cart_quote, safe_checkout
from app.api.v1.routes.geography import _serviceability
from app.models.orders import Cart, CartItem
from app.schemas.orders import CheckoutRequest
from app.services.spatial import point_is_in_service_area, serviceability_for_point
from tests import factories


def test_overlapping_zones_admit_covered_address_and_reject_outside_checkout() -> None:
    with factories.session() as db:
        near_hub = factories.make_village(db)
        near_hub.latitude, near_hub.longitude = 5.0, 5.001
        near_zone = factories.make_service_area(db, near_hub)
        near_zone.radius_km = 0.05  # ~110 m away, but covers only 50 m

        covering_hub = factories.make_village(db)
        covering_hub.latitude, covering_hub.longitude = 5.0, 5.02
        covering_zone = factories.make_service_area(db, covering_hub)
        covering_zone.radius_km = 4.0  # ~2.2 km away, but covers this pin

        customer = factories.make_user(db)
        store = factories.make_store(
            db, village=covering_hub, service_area=covering_zone,
            latitude=5.0, longitude=5.02, is_active=True,
        )
        listing = factories.make_listing(db, store)
        address = factories.make_address(db, customer, covering_hub)
        address.latitude, address.longitude = 5.0, 5.0

        cart = Cart(user_id=customer.id, store_id=store.id)
        db.add(cart)
        db.flush()
        item = CartItem(cart_id=cart.id, store_product_id=listing.id, quantity=1)
        db.add(item)
        db.commit()

        try:
            # Before the fix, the nearest 50-m zone won and returned false.
            best = serviceability_for_point(db, 5.0, 5.0)
            assert best is not None
            assert best["id"] == covering_zone.id
            assert best["covers_point"] is True
            assert point_is_in_service_area(db, near_zone.id, 5.0, 5.0) is False
            assert point_is_in_service_area(db, covering_zone.id, 5.0, 5.0) is True
            assert _serviceability(db, 5.0, 5.0).serviceable is True

            quote = cart_quote(address.id, db=db, user=customer)
            assert quote.serviceable is True
            assert quote.checkout_ready is True

            # A genuinely out-of-zone address must still fail both admission
            # and the authoritative place-order mutation.
            address.latitude, address.longitude = 5.2, 5.2
            db.flush()
            assert _serviceability(db, 5.2, 5.2).serviceable is False
            outside_quote = cart_quote(address.id, db=db, user=customer)
            assert outside_quote.serviceable is False
            assert outside_quote.checkout_ready is False
            with pytest.raises(HTTPException) as error:
                safe_checkout(
                    CheckoutRequest(address_id=address.id),
                    idempotency_key=str(uuid4()), db=db, user=customer,
                )
            assert error.value.status_code == 409
            assert "does not deliver" in error.value.detail
        finally:
            db.rollback()
            db.delete(item)
            db.delete(cart)
            db.delete(address)
            db.commit()
