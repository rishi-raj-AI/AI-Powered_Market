"""Invalid commercial totals must never authorize automatic UPI stock recovery.

Provider reads are mocked; records are disposable test fixtures.
"""
from decimal import Decimal

import pytest

from app.models.commerce import StoreProduct
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import session
from tests.test_payment_expiration import _old_unpaid_order


@pytest.mark.parametrize("invalid_total", [Decimal("0.00"), Decimal("-1.00")])
def test_invalid_order_total_defers_without_provider_lookup_or_stock_release(
    monkeypatch, invalid_total,
):
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)
        order = db.get(Order, order_id)
        order.total = invalid_total
        db.commit()

        def unexpected_provider_call(**_kwargs):
            raise AssertionError("invalid order must not be reconciled with provider")

        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments", unexpected_provider_call,
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        db.expire_all()
        order = db.get(Order, order_id)
        assert result["expired"] == 0
        assert result["captured"] == 0
        assert result["deferred"] >= 1
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
