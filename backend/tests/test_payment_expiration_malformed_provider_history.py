"""Malformed Razorpay history must never release an unpaid reservation.

These are database-backed regression scenarios with a mocked provider; no live
payment or refund API is invoked.
"""
from app.models.commerce import StoreProduct
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import session

from tests.test_payment_expiration import _old_unpaid_order


def test_non_mapping_provider_history_defers_expiration(monkeypatch):
    with session() as db:
        order_id, _, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [None],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        order = db.get(Order, order_id)
        assert result["deferred"] >= 1
        assert result["expired"] == 0
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


def test_malformed_failed_history_cannot_prove_nonpayment(monkeypatch):
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": "pay_malformed_history",
                "order_id": provider_order_id,
                "status": "failed",
                "amount": True,  # bool must not be accepted as an integer amount
                "currency": "INR",
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        order = db.get(Order, order_id)
        assert result["deferred"] >= 1
        assert result["expired"] == 0
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
