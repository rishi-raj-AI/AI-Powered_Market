"""Regression: deferred payment attempts must not starve later safe expirations.

Expected failure documents the current invocation-local cursor defect. Do not
remove xfail until durable progress is implemented and tested on PostgreSQL.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import make_order, session
from tests.test_payment_expiration import _old_unpaid_order


@pytest.mark.xfail(
    strict=True,
    reason="bounded scan restarts at oldest deferred payment attempts on every invocation",
)
def test_deferred_attempt_backlog_does_not_starve_later_safe_reservation(monkeypatch):
    with session() as db:
        old = datetime.now(timezone.utc) - timedelta(hours=4)
        for offset in range(501):
            order = make_order(
                db, payment_status=PaymentStatus.PENDING,
                with_paid_attempt=False,
            )
            order.created_at = old + timedelta(microseconds=offset)
            # An unresolved provider intent must never be cancelled, but it
            # also must not permanently prevent processing later safe orders.
            db.add(PaymentAttempt(
                order_id=order.id, provider="razorpay",
                provider_order_id=f"order_{uuid4().hex}",
                status="authorized", amount=Decimal("120.00"),
                currency="INR", created_at=old,
            ))
        db.commit()

        target_id, target_provider_order_id, _ = _old_unpaid_order(db)
        target = db.get(Order, target_id)
        target.created_at = old + timedelta(minutes=1)
        db.commit()

        queried = []

        def provider_history(*, provider_order_id):
            queried.append(provider_order_id)
            return []

        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments", provider_history,
        )
        for _ in range(2):
            payment_expiration.expire_unpaid_orders(db, limit=1)

        assert target_provider_order_id in queried
        assert db.get(Order, target_id).status == OrderStatus.CANCELLED
