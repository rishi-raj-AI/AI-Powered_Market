"""PostGIS-backed P0 checkout eligibility and diagnostic regression tests."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.v1.routes.checkout import cart_quote, safe_checkout
from app.models.orders import Cart, CartItem, Order
from app.schemas.orders import CheckoutRequest
from app.scripts.diagnose_delivery_serviceability import diagnose
from app.services.delivery_serviceability import evaluate_delivery
from tests import factories


def _cart_for(db, customer, store):
    listing = factories.make_listing(db, store)
    cart = Cart(user_id=customer.id, store_id=store.id)
    db.add(cart)
    db.flush()
    factories._track(cart)
    item = CartItem(cart_id=cart.id, store_product_id=listing.id, quantity=1)
    db.add(item)
    db.flush()
    factories._track(item)


def test_unpinned_legacy_address_never_inherits_village_centroid_for_checkout():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(db, customer, db.get(factories.Village, store.village_id))
        address.latitude = None
        address.longitude = None
        _cart_for(db, customer, store)
        db.commit()

        before = db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id))
        quote = cart_quote(address.id, db=db, user=customer)
        assert quote.serviceable is False
        assert quote.serviceability_reason_code == "ADDRESS_COORDINATES_MISSING"
        assert "Confirm your delivery location" in quote.blockers[0]
        with pytest.raises(HTTPException) as exc:
            safe_checkout(
                CheckoutRequest(address_id=address.id),
                idempotency_key=str(uuid4()), db=db, user=customer,
            )
        assert exc.value.status_code == 409
        assert db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id)) == before

        diagnostic = diagnose(db, store.id, address.id)
        assert diagnostic["village_fallback_would_be_used_by_old_checkout"] is True
        assert diagnostic["legacy_locality_fallback_inside_area"] is True
        assert diagnostic["serviceable"] is False
        assert diagnostic["reason_code"] == "ADDRESS_COORDINATES_MISSING"
        assert "latitude" not in diagnostic and "longitude" not in diagnostic
        assert "phone" not in diagnostic and "landmark" not in diagnostic
        db.rollback()


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("disabled", "STORE_DELIVERY_DISABLED"),
        ("no_assignment", "STORE_TERRITORY_MISSING"),
        ("inactive_area", "TERRITORY_INACTIVE"),
        ("outside", "ADDRESS_OUTSIDE_TERRITORY"),
        ("inactive_store", "STORE_UNAVAILABLE"),
        ("invalid_address", "ADDRESS_LOCATION_UNCONFIRMED"),
    ],
)
def test_delivery_decision_reason_codes(change, expected):
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(db, customer, db.get(factories.Village, store.village_id))
        area = db.get(factories.ServiceArea, store.service_area_id)
        if change == "disabled":
            store.delivery_enabled = False
        elif change == "no_assignment":
            store.service_area_id = None
        elif change == "inactive_area":
            area.is_active = False
        elif change == "outside":
            address.latitude, address.longitude = 28.6139, 77.2090
        elif change == "inactive_store":
            store.is_active = False
        elif change == "invalid_address":
            address.latitude = 91.0
        db.flush()
        decision = evaluate_delivery(db, store, address)
        assert decision.serviceable is False
        assert decision.reason_code == expected
        assert decision.matched_territory_id is None
        db.rollback()


def test_postgis_radius_stays_hub_centered_and_does_not_expand_to_store_pin():
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
        address = factories.make_address(db, customer, hub)
        address.latitude, address.longitude = 0.0, 0.0091
        db.flush()
        outside = evaluate_delivery(db, store, address)
        assert outside.reason_code == "ADDRESS_OUTSIDE_TERRITORY"
        address.longitude = 0.0089
        db.flush()
        inside = evaluate_delivery(db, store, address)
        assert inside.serviceable is True
        assert inside.matched_territory_id == area.id
        assert inside.location_confidence == "legacy_coordinates"
        db.rollback()


def test_diagnostic_reports_only_scoped_configuration_and_rounded_distances():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(db, customer, db.get(factories.Village, store.village_id))
        db.flush()
        result = diagnose(db, store.id, address.id)
        assert result["found"] is True
        assert result["serviceable"] is True
        assert result["address_inside_assigned_area"] is True
        assert result["hub_to_address_km"] == 0.0
        assert result["service_area_id"] == str(store.service_area_id)
        assert set(result).isdisjoint({
            "recipient_name", "phone", "house_details", "landmark",
            "latitude", "longitude", "customer_id",
        })
        db.rollback()


def test_provenance_is_confirmed_only_with_source_and_server_timestamp():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        db.flush()
        assert evaluate_delivery(db, store, address).location_confidence == "legacy_coordinates"
        # These attributes become mapped nullable fields in additive PR #247.
        # Until then, getattr keeps the P0 engine compatible with the old schema.
        address.location_source = "gps"
        unconfirmed = evaluate_delivery(db, store, address)
        assert unconfirmed.location_confidence == "unconfirmed_gps"
        assert unconfirmed.reason_code == "ADDRESS_LOCATION_UNCONFIRMED"
        assert unconfirmed.serviceable is False
        address.location_confirmed_at = datetime.now(timezone.utc)
        assert evaluate_delivery(db, store, address).location_confidence == "confirmed_gps"
        address.location_source = "map_pin"
        assert evaluate_delivery(db, store, address).location_confidence == "confirmed_map_pin"
        # A Places centroid is approximate even if a client saved it and the
        # backend timestamped that event; it is not a doorstep confirmation.
        address.location_source = "searched_place"
        approximate = evaluate_delivery(db, store, address)
        assert approximate.location_confidence == "approximate_searched_place"
        assert approximate.reason_code == "ADDRESS_LOCATION_UNCONFIRMED"
        assert approximate.serviceable is False
        db.rollback()


def test_searched_place_centroid_cannot_create_order_even_inside_territory():
    """Quote and authoritative checkout both require a deliberate pin."""
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        _cart_for(db, customer, store)
        db.commit()
        # PR #247 maps this optional attribute to the provenance column.
        address.location_source = "searched_place"
        before = db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id))
        quote = cart_quote(address.id, db=db, user=customer)
        assert quote.serviceable is False
        assert quote.checkout_ready is False
        assert quote.serviceability_reason_code == "ADDRESS_LOCATION_UNCONFIRMED"
        with pytest.raises(HTTPException) as exc:
            safe_checkout(
                CheckoutRequest(address_id=address.id),
                idempotency_key=str(uuid4()), db=db, user=customer,
            )
        assert exc.value.status_code == 409
        assert db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id)) == before
        db.rollback()


@pytest.mark.parametrize("source", ["imported_centroid", "legacy", "", "GPS"])
def test_unknown_non_null_provenance_never_inherits_legacy_checkout(source):
    """Only a NULL provenance record may use historical coordinate compatibility."""
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        address = factories.make_address(
            db, customer, db.get(factories.Village, store.village_id),
        )
        _cart_for(db, customer, store)
        db.commit()
        address.location_source = source
        address.location_confirmed_at = datetime.now(timezone.utc)
        decision = evaluate_delivery(db, store, address)
        assert decision.serviceable is False
        assert decision.reason_code == "ADDRESS_LOCATION_UNCONFIRMED"
        assert decision.location_confidence == "unrecognized_location_source"
        before = db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id))
        quote = cart_quote(address.id, db=db, user=customer)
        assert quote.serviceable is False
        assert quote.serviceability_reason_code == "ADDRESS_LOCATION_UNCONFIRMED"
        with pytest.raises(HTTPException) as exc:
            safe_checkout(
                CheckoutRequest(address_id=address.id),
                idempotency_key=str(uuid4()), db=db, user=customer,
            )
        assert exc.value.status_code == 409
        assert db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id)) == before
        db.rollback()
