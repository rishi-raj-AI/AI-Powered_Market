"""Cross-branch persistence regression: serviceability must read persisted provenance."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.v1.routes.checkout import cart_quote, safe_checkout
from app.models.geography import Address
from app.models.orders import Cart, CartItem, Order, PaymentMethod
from app.schemas.orders import CheckoutRequest
from app.services.delivery_serviceability import evaluate_delivery
from tests import factories


def test_persisted_searched_place_cannot_be_treated_as_legacy_pin():
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        village = db.get(factories.Village, store.village_id)
        address = factories.make_address(db, customer, village)
        address.location_source = "searched_place"
        address.location_confirmed_at = None
        db.commit()
        db.expire_all()
        persisted = db.get(Address, address.id)
        assert persisted.location_source == "searched_place"
        decision = evaluate_delivery(db, store, persisted)
        assert decision.reason_code == "ADDRESS_LOCATION_UNCONFIRMED"
        assert decision.location_confidence == "approximate_searched_place"
        db.rollback()


def test_persisted_confirmed_pin_is_distinct_from_legacy_coordinates():
    from datetime import datetime, timezone

    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        village = db.get(factories.Village, store.village_id)
        address = factories.make_address(db, customer, village)
        address.location_source = "map_pin"
        address.location_confirmed_at = datetime.now(timezone.utc)
        db.commit()
        db.expire_all()
        persisted = db.get(Address, address.id)
        decision = evaluate_delivery(db, store, persisted)
        assert decision.location_confidence == "confirmed_map_pin"
        assert decision.reason_code == "SERVICEABLE"
        db.rollback()


@pytest.mark.parametrize("payment_method", [PaymentMethod.COD, PaymentMethod.UPI])
def test_persisted_provider_centroid_rejected_at_quote_and_order_creation(payment_method):
    """Reject after DB reload; no order, stock reservation or payment intent."""
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        village = db.get(factories.Village, store.village_id)
        address = factories.make_address(db, customer, village)
        listing = factories.make_listing(db, store, stock=5)
        cart = Cart(user_id=customer.id, store_id=store.id)
        db.add(cart)
        db.flush()
        factories._track(cart)
        item = CartItem(cart_id=cart.id, store_product_id=listing.id, quantity=1)
        db.add(item)
        db.flush()
        factories._track(item)
        address.location_source = "searched_place"
        address.location_confirmed_at = None
        db.commit()
        db.expire_all()

        quote = cart_quote(address.id, db=db, user=customer)
        assert quote.serviceable is False
        assert quote.serviceability_reason_code == "ADDRESS_LOCATION_UNCONFIRMED"
        assert quote.checkout_ready is False
        before = db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id))
        stock_before = listing.stock_quantity
        with pytest.raises(HTTPException) as exc:
            safe_checkout(
                CheckoutRequest(address_id=address.id, payment_method=payment_method),
                idempotency_key=str(uuid4()),
                db=db,
                user=customer,
            )
        assert exc.value.status_code == 409
        assert db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id)) == before
        assert listing.stock_quantity == stock_before
        db.rollback()
