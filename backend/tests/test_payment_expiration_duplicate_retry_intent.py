"""Duplicate Razorpay retry intent identities must not authorize stock release.

Disposable database fixtures and mocked provider I/O only.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.models.commerce import StoreProduct
from app.services import payment_expiration
from tests.factories import session
from tests.test_payment_expiration import _old_unpaid_order


def test_duplicate_provider_order_id_defers_even_with_empty_history(monkeypatch):
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        db.add(PaymentAttempt(
            order_id=order_id,
            provider="razorpay",
            provider_order_id=provider_order_id,
            status="failed",
            amount=Decimal("120.00"),
            currency="INR",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        ))
        db.commit()
        requested = []

        def history(*, provider_order_id):
            requested.append(provider_order_id)
            return []

        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", history)
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        order = db.get(Order, order_id)
        assert result["expired"] == 0
        assert result["captured"] == 0
        assert result["deferred"] >= 1
        assert requested == [provider_order_id]
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
