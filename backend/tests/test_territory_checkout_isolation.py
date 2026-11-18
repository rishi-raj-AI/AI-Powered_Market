"""Regression: an active preview territory never overrides legacy checkout coverage.

Uses synthetic PostGIS rows and local order/payment models only. No provider calls.
"""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.v1.routes.checkout import cart_quote, safe_checkout
from app.core.config import settings
from app.models.orders import Order, PaymentMethod
from app.schemas.orders import CheckoutRequest
from app.services.delivery_serviceability import evaluate_delivery
from app.services.territory_preview import match_active_store_territory
from tests import factories
from tests.test_payment_geography_checkout_gate import _setup_cart
from tests.test_territory_preview import _active_territory


@pytest.mark.parametrize("payment_method", [PaymentMethod.COD, PaymentMethod.UPI])
def test_preview_territory_and_admin_flags_never_expand_checkout_coverage(
    monkeypatch, payment_method,
):
    # These opt-in flags must never select the new engine for checkout.
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PREVIEW_ENABLED", True)
    monkeypatch.setattr(settings, "TERRITORY_ADMIN_PUBLISH_ENABLED", True)
    with factories.session() as db:
        customer, store, address, listing = _setup_cart(db)
        # The synthetic preview territory covers (0, 0), but the store's
        # authoritative legacy service area does not.
        address.latitude = 0
        address.longitude = 0
        _active_territory(db, store)
        db.flush()

        assert match_active_store_territory(db, store.id, 0, 0) is not None
        decision = evaluate_delivery(db, store, address)
        assert decision.serviceable is False
        assert decision.reason_code == "ADDRESS_OUTSIDE_TERRITORY"

        quote = cart_quote(address.id, db=db, user=customer)
        assert quote.serviceable is False
        assert quote.checkout_ready is False
        assert quote.serviceability_reason_code == "ADDRESS_OUTSIDE_TERRITORY"

        count_before = db.scalar(
            select(func.count(Order.id)).where(Order.user_id == customer.id)
        )
        stock_before = listing.stock_quantity
        with pytest.raises(HTTPException) as error:
            safe_checkout(
                CheckoutRequest(
                    address_id=address.id,
                    payment_method=payment_method,
                ),
                idempotency_key=str(uuid4()),
                db=db,
                user=customer,
            )
        assert error.value.status_code == 409
        assert db.scalar(
            select(func.count(Order.id)).where(Order.user_id == customer.id)
        ) == count_before
        assert listing.stock_quantity == stock_before
        db.rollback()
