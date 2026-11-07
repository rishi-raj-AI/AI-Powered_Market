"""Payment-expiration reconciliation must be atomic and fail closed.

Provider responses are mocked; these tests never call real payment APIs.
"""
from uuid import uuid4

from app.models.commerce import StoreProduct
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import session
from tests.test_payment_expiration import _old_unpaid_order


def test_capture_notification_failure_rolls_back_paid_transition(monkeypatch):
    """An outbox failure must not leave half-committed paid evidence."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        payment_id = f"pay_{uuid4().hex}"
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": payment_id, "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": "captured",
            }],
        )

        def mark_paid(_db, attempt, order, captured_id):
            attempt.status = "paid"
            attempt.provider_payment_id = captured_id
            order.payment_status = PaymentStatus.PAID

        def fail_outbox(_db, _order):
            raise RuntimeError("simulated outbox write failure")

        monkeypatch.setattr(payment_expiration, "_apply_paid", mark_paid)
        monkeypatch.setattr(payment_expiration, "_notify_payment_captured", fail_outbox)
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        db.expire_all()
        order = db.get(Order, order_id)
        assert result["captured"] == 0
        assert result["expired"] == 0
        assert result["deferred"] >= 1
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


def test_distinct_multiple_captures_require_manual_reconciliation(monkeypatch):
    """Two captured payments must never auto-confirm or release the reservation."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [
                {
                    "id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                    "amount": 12000, "currency": "INR", "status": "captured",
                }
                for _ in range(2)
            ],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        order = db.get(Order, order_id)
        assert result["captured"] == 0
        assert result["expired"] == 0
        assert result["deferred"] >= 1
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
