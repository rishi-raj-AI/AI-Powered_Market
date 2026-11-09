"""Regression: a closer hub with a smaller radius must not block a covering zone.

Uses the same real PostGIS database as Backend CI. No mocked geometry: this
reproduces the previous address-admission versus checkout disagreement.
"""

import pytest
from fastapi import HTTPException

from app.api.v1.routes.checkout import cart_quote
from app.api.v1.routes.geography import _serviceability, create_my_address
from app.models.orders import Cart, CartItem
from app.schemas.geography import AddressCreate
from app.services.spatial import point_is_in_service_area, serviceability_for_point
from tests import factories


def test_overlapping_zones_require_store_assigned_covering_area() -> None:
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

        saved_address = None
        try:
            # Before the fix, the nearest 50-m zone won and returned false.
            best = serviceability_for_point(db, 5.0, 5.0)
            assert best is not None
            assert best["id"] == covering_zone.id
            assert best["covers_point"] is True
            assert point_is_in_service_area(db, near_zone.id, 5.0, 5.0) is False
            assert point_is_in_service_area(db, covering_zone.id, 5.0, 5.0) is True
            assert _serviceability(db, 5.0, 5.0).serviceable is True
            saved_address = create_my_address(
                AddressCreate(
                    village_id=covering_hub.id, landmark="Covered entrance",
                    latitude=5.0, longitude=5.0,
                ),
                db=db, user=customer,
            )
            assert saved_address.id is not None

            quote = cart_quote(address.id, db=db, user=customer)
            assert quote.serviceable is True
            assert quote.checkout_ready is True

            # The assigned non-covering area must reject checkout even when
            # a different active service area covers the customer.
            store.service_area_id = near_zone.id
            db.flush()
            assert point_is_in_service_area(db, near_zone.id, 5.0, 5.0) is False
            assert cart_quote(address.id, db=db, user=customer).serviceable is False
            store.service_area_id = covering_zone.id
            db.flush()

            # A genuinely out-of-zone address must still fail both admission
            # and the authoritative place-order mutation.
            address.latitude, address.longitude = 5.2, 5.2
            db.flush()
            assert _serviceability(db, 5.2, 5.2).serviceable is False
            with pytest.raises(HTTPException) as address_error:
                create_my_address(
                    AddressCreate(
                        village_id=covering_hub.id, landmark="Outside entrance",
                        latitude=5.2, longitude=5.2,
                    ),
                    db=db, user=customer,
                )
            assert address_error.value.status_code == 422
            outside_quote = cart_quote(address.id, db=db, user=customer)
            assert outside_quote.serviceable is False
            assert outside_quote.checkout_ready is False
        finally:
            db.rollback()
            if saved_address is not None:
                db.delete(saved_address)
            db.delete(item)
            db.delete(cart)
            db.delete(address)
            db.commit()
