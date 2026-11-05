"""Cross-attempt expiration invariants for UPI retry windows.

Uses disposable database fixtures and mocked provider history; no live payment calls.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.models.commerce import StoreProduct
from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import session
from tests.test_payment_expiration import _old_unpaid_order


def test_recent_retry_preserves_old_order_stock_without_provider_io(monkeypatch):
    """An old order is not expired while its newest provider intent is fresh."""
    with session() as db:
        order_id, _, listing_id = _old_unpaid_order(db)
        db.add(PaymentAttempt(
            order_id=order_id, provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            status="created", amount=Decimal("120.00"), currency="INR",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()

        def unexpected_provider_read(**_kwargs):
            raise AssertionError("recent retry must defer before provider IO")

        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            unexpected_provider_read,
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        order = db.get(Order, order_id)
        assert result["expired"] == 0
        assert result["captured"] == 0
        assert result["deferred"] >= 1
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


def test_failed_old_attempt_does_not_hide_captured_retry(monkeypatch):
    """Captured retry must win over a previous failed provider attempt."""
    with session() as db:
        order_id, first_provider_order, listing_id = _old_unpaid_order(db)
        retry_provider_order = f"order_{uuid4().hex}"
        db.add(PaymentAttempt(
            order_id=order_id, provider="razorpay",
            provider_order_id=retry_provider_order,
            status="attempted", amount=Decimal("120.00"), currency="INR",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=40),
        ))
        db.commit()
        calls = []

        def history(*, provider_order_id):
            calls.append(provider_order_id)
            return [{
                "id": f"pay_{uuid4().hex}",
                "order_id": provider_order_id,
                "amount": 12000, "currency": "INR",
                "status": "failed" if provider_order_id == first_provider_order else "captured",
            }]

        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", history)
        monkeypatch.setattr(payment_expiration, "_notify_payment_captured", lambda *_: None)

        def apply_paid(_db, attempt, order, payment_id):
            attempt.status = "paid"
            attempt.provider_payment_id = payment_id
            order.payment_status = PaymentStatus.PAID

        monkeypatch.setattr(payment_expiration, "_apply_paid", apply_paid)
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        order = db.get(Order, order_id)
        assert set(calls) == {first_provider_order, retry_provider_order}
        assert result["captured"] == 1
        assert result["expired"] == 0
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PAID
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
