"""Known cross-invocation fairness gap in the unpaid-UPI expiration scanner.

This is an executable acceptance target, deliberately marked xfail until a
persisted, concurrency-safe scan cursor (or equivalent retry scheduling) exists.
Provider I/O is mocked and all records are disposable.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import make_order, session
from tests.test_payment_expiration import _old_unpaid_order


@pytest.mark.xfail(
    strict=True,
    reason="Expiration scan cursor resets between invocations; old deferred rows starve later eligible rows",
)
def test_repeated_expiration_invocations_reach_order_beyond_deferred_scan_budget(monkeypatch):
    with session() as db:
        old = datetime.now(timezone.utc) - timedelta(hours=4)
        for offset in range(501):
            order = make_order(
                db, payment_status=PaymentStatus.PENDING,
                with_paid_attempt=False,
            )
            order.created_at = old + timedelta(microseconds=offset)
        db.commit()

        target_id, provider_order_id, _ = _old_unpaid_order(db)
        target = db.get(Order, target_id)
        target.created_at = old + timedelta(minutes=1)
        db.commit()

        calls = []

        def provider_history(*, provider_order_id):
            calls.append(provider_order_id)
            return []

        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments", provider_history,
        )
        for _ in range(2):
            payment_expiration.expire_unpaid_orders(db, limit=1)

        # Must eventually advance beyond the same 500 deferred rows.
        assert provider_order_id in calls
        assert db.get(Order, target_id).status == OrderStatus.CANCELLED
