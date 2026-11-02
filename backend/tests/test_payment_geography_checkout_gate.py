"""Payment/geography integration: checkout must not bypass authorized coverage.

Run against CI PostgreSQL/PostGIS; both quote and order mutation are tested
for COD and UPI without making a provider call.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.v1.routes.checkout import cart_quote, safe_checkout
from app.models.orders import Cart, CartItem, Order, PaymentMethod
from app.schemas.orders import CheckoutRequest
from app.services.delivery_serviceability import evaluate_delivery
from tests import factories


def _setup_cart(db):
    customer = factories.make_user(db)
    store = factories.make_store(db, is_active=True)
    address = factories.make_address(db, customer, db.get(factories.Village, store.village_id))
    listing = factories.make_listing(db, store, stock=5)
    cart = Cart(user_id=customer.id, store_id=store.id)
    db.add(cart)
    db.flush()
    factories._track(cart)
    item = CartItem(cart_id=cart.id, store_product_id=listing.id, quantity=1)
    db.add(item)
    db.flush()
    factories._track(item)
    return customer, store, address, listing


@pytest.mark.parametrize("payment_method", [PaymentMethod.COD, PaymentMethod.UPI])
@pytest.mark.parametrize(
    ("scenario", "reason"),
    [
        ("missing_pin", "ADDRESS_COORDINATES_MISSING"),
        ("outside", "ADDRESS_OUTSIDE_TERRITORY"),
        ("inactive_area", "TERRITORY_INACTIVE"),
        ("no_assignment", "STORE_TERRITORY_MISSING"),
        ("delivery_disabled", "STORE_DELIVERY_DISABLED"),
        ("searched_place", "ADDRESS_LOCATION_UNCONFIRMED"),
    ],
)
def test_checkout_rejects_unserviceable_without_order_or_stock_change(scenario, reason, payment_method):
    with factories.session() as db:
        customer, store, address, listing = _setup_cart(db)
        if scenario == "missing_pin":
            address.latitude = None
            address.longitude = None
        elif scenario == "outside":
            address.latitude, address.longitude = 28.6139, 77.2090
        elif scenario == "inactive_area":
            db.get(factories.ServiceArea, store.service_area_id).is_active = False
        elif scenario == "no_assignment":
            store.service_area_id = None
        elif scenario == "delivery_disabled":
            store.delivery_enabled = False
        elif scenario == "searched_place":
            address.location_source = "searched_place"
        db.flush()
        decision = evaluate_delivery(db, store, address)
        assert decision.serviceable is False
        assert decision.reason_code == reason
        quote = cart_quote(address.id, db=db, user=customer)
        assert quote.serviceable is False
        assert quote.checkout_ready is False
        assert quote.blockers
        before = db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id))
        stock_before = listing.stock_quantity
        with pytest.raises(HTTPException) as error:
            safe_checkout(
                CheckoutRequest(address_id=address.id, payment_method=payment_method),
                idempotency_key=str(uuid4()),
                db=db,
                user=customer,
            )
        assert error.value.status_code == 409
        assert db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id)) == before
        assert listing.stock_quantity == stock_before
        db.rollback()


def test_inside_assigned_hub_area_is_eligible_without_expanding_coverage():
    with factories.session() as db:
        customer, store, address, _listing = _setup_cart(db)
        decision = evaluate_delivery(db, store, address)
        assert decision.serviceable is True
        assert decision.matched_territory_id == store.service_area_id
        quote = cart_quote(address.id, db=db, user=customer)
        assert quote.serviceable is True
        assert quote.checkout_ready is True
        db.rollback()


def test_unconfirmed_gps_does_not_inherit_legacy_coordinate_compatibility():
    with factories.session() as db:
        customer, store, address, _listing = _setup_cart(db)
        address.location_source = "gps"
        assert evaluate_delivery(db, store, address).reason_code == "ADDRESS_LOCATION_UNCONFIRMED"
        quote = cart_quote(address.id, db=db, user=customer)
        assert quote.serviceable is False
        db.rollback()
