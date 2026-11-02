"""PostGIS release acceptance for active delivery-radius boundaries.

The repository currently models service areas as hub-centered geography
circles, not polygons. These tests exercise the real SQL predicate and reject
out-of-radius coordinates; they must run against CI PostGIS, not mocks.
"""


from app.api.v1.routes.checkout import cart_quote
from app.models.orders import Cart, CartItem
from app.services.spatial import point_is_in_service_area, serviceability_for_point
from tests import factories


def test_serviceability_respects_radius_boundary_and_activation() -> None:
    with factories.session() as db:
        hub = factories.make_village(db)
        hub.latitude, hub.longitude = 0.0, 0.0
        area = factories.make_service_area(db, hub)
        area.radius_km = 1.0
        db.flush()

        # At the equator, 0.0089° longitude is ~991 m and 0.0091° is
        # ~1013 m. Both points straddle the 1-km boundary by > 8 m.
        assert point_is_in_service_area(db, area.id, 0.0, 0.0089) is True
        assert point_is_in_service_area(db, area.id, 0.0, 0.0091) is False
        inside = serviceability_for_point(db, 0.0, 0.0089)
        outside = serviceability_for_point(db, 0.0, 0.0091)
        assert inside is not None and inside["id"] == area.id
        assert inside["covers_point"] is True
        assert outside is not None and outside["covers_point"] is False

        # A formerly covering area must immediately cease to authorize
        # checkout when disabled, even if its geometry has not changed.
        area.is_active = False
        db.flush()
        assert point_is_in_service_area(db, area.id, 0.0, 0.0089) is False

        area.is_active = True
        hub.is_active = False
        db.flush()
        assert point_is_in_service_area(db, area.id, 0.0, 0.0089) is False
        db.rollback()


def test_checkout_quote_rejects_outside_hub_radius() -> None:
    """A store pin near the customer must not expand the assigned hub radius."""
    with factories.session() as db:
        hub = factories.make_village(db)
        hub.latitude, hub.longitude = 0.0, 0.0
        area = factories.make_service_area(db, hub)
        area.radius_km = 1.0
        customer = factories.make_user(db)
        store = factories.make_store(
            db, village=hub, service_area=area,
            latitude=0.0, longitude=0.0089, is_active=True,
        )
        listing = factories.make_listing(db, store)
        address = factories.make_address(db, customer, hub)
        # Only ~22 m from the store, but >1 km from the zone hub.
        address.latitude, address.longitude = 0.0, 0.0091
        cart = Cart(user_id=customer.id, store_id=store.id)
        db.add(cart)
        db.flush()
        item = CartItem(cart_id=cart.id, store_product_id=listing.id, quantity=1)
        db.add(item)
        db.commit()

        try:
            assert point_is_in_service_area(db, area.id, 0.0, 0.0091) is False
            assert cart_quote(address.id, db=db, user=customer).serviceable is False
            db.rollback()

            address.longitude = 0.0089
            db.flush()
            quote = cart_quote(address.id, db=db, user=customer)
            assert quote.serviceable is True
            assert quote.checkout_ready is True
        finally:
            db.rollback()
            db.delete(item)
            db.delete(cart)
            db.delete(address)
            db.commit()
