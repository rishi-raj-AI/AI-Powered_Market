"""Unknown payment-provider attempts must block automatic UPI stock release.

The provider-history mock is intentionally empty: a Razorpay-only lookup cannot
prove that an unexpected second payment provider did not move money.
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


def test_unknown_provider_attempt_defers_expiry_despite_empty_razorpay_history(monkeypatch):
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)
        db.add(PaymentAttempt(
            order_id=order_id,
            provider="unrecognized_provider",
            provider_order_id=f"other_{uuid4().hex}",
            status="attempted",
            amount=Decimal("120.00"),
            currency="INR",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=40),
        ))
        db.commit()
        calls = []
        def empty_history(**kwargs):
            calls.append(kwargs)
            return []
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments", empty_history
        )

        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        order = db.get(Order, order_id)

        assert result["deferred"] >= 1
        assert result["expired"] == 0
        assert result["captured"] == 0
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
        # No single provider's empty history can establish global nonpayment.
        assert len(calls) == 1
