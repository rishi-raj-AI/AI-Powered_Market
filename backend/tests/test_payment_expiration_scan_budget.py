"""Regression for deferred legacy orders starving later expiration candidates."""
from datetime import datetime, timedelta, timezone

from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import make_order, session


def test_expiry_scans_past_deferred_legacy_orders(monkeypatch):
    with session() as db:
        old = datetime.now(timezone.utc) - timedelta(minutes=45)
        deferred_ids = []
        for _ in range(3):
            order = make_order(db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False)
            order.created_at = old - timedelta(minutes=5)
            deferred_ids.append(order.id)
        eligible = make_order(db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False)
        eligible.created_at = old
        db.add(PaymentAttempt(
            order_id=eligible.id, provider="razorpay", provider_order_id="order_scan_budget_test",
            status="attempted", amount=eligible.total, currency="INR",
            created_at=old,
        ))
        db.commit()
        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", lambda **_: [])
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        assert result["expired"] == 1
        assert result["deferred"] >= 3
        assert result["considered"] >= 4
        assert db.get(Order, eligible.id).status == OrderStatus.CANCELLED
        for order_id in deferred_ids:
            assert db.get(Order, order_id).status == OrderStatus.PLACED
