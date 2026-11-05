"""Expiration must commit stock restoration and cancellation notification atomically.

All provider responses are mocked. Fixtures use disposable test database records.
"""
from app.models.commerce import StoreProduct
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import session
from tests.test_payment_expiration import _old_unpaid_order


def test_expiry_notification_outbox_failure_preserves_order_and_reserved_stock(monkeypatch):
    """An outbox write failure must roll back the stock restoration as well."""
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments", lambda **_: [],
        )

        def fail_outbox(*_args, **_kwargs):
            raise RuntimeError("simulated notification outbox failure")

        monkeypatch.setattr(payment_expiration, "enqueue_notification", fail_outbox)
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
