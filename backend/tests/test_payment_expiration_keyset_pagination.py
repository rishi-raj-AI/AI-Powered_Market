"""Regression for keyset pagination across deferred unpaid UPI reservations.

All rows are disposable test fixtures; provider history is mocked.
"""
from datetime import datetime, timedelta, timezone

from app.models.orders import OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import make_order, session
from tests.test_payment_expiration import _old_unpaid_order


def test_expiry_pages_past_full_batch_of_unreconcilable_legacy_orders(monkeypatch):
    with session() as db:
        # A limit of one scans batches of at least 25. Older orders without
        # attempts must not permanently hide a later, provably unpaid order.
        old = datetime.now(timezone.utc) - timedelta(hours=3)
        deferred_ids = []
        for offset in range(26):
            order = make_order(
                db, payment_status=PaymentStatus.PENDING,
                with_paid_attempt=False,
            )
            order.created_at = old + timedelta(seconds=offset)
            deferred_ids.append(order.id)
        db.commit()

        target_id, _, _ = _old_unpaid_order(db)
        target = db.get(type(order), target_id)
        target.created_at = old + timedelta(minutes=1)
        db.commit()

        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        assert result["considered"] >= 27
        assert result["deferred"] >= 26
        assert result["expired"] == 1
        assert db.get(type(order), target_id).status == OrderStatus.CANCELLED
        assert all(
            db.get(type(order), order_id).status == OrderStatus.PLACED
            for order_id in deferred_ids
        )
