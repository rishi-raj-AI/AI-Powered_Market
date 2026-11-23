"""Cross-invocation fairness checks for the unpaid-UPI expiration scanner.

The no-attempt legacy backlog must not consume the bounded scan budget.
Other kinds of deferred records still require durable retry scheduling.
Provider I/O is mocked and all records are disposable.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.services.payments import PaymentProviderUnavailable

from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import make_order, session
from tests.test_payment_expiration import _old_unpaid_order


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


@pytest.mark.xfail(
    strict=True,
    reason="Provider-deferred attempts still starve later orders across scanner invocations",
)
def test_provider_deferred_backlog_does_not_starve_later_unpaid_order(monkeypatch):
    """Real payment attempts, unlike no-attempt legacy rows, remain candidates.

    A repeated provider outage for older orders must not permanently prevent
    a later independently reconcilable reservation from being processed.
    """
    with session() as db:
        old = datetime.now(timezone.utc) - timedelta(hours=4)
        deferred_provider_ids = set()
        for offset in range(501):
            order_id, provider_order_id, _ = _old_unpaid_order(db)
            order = db.get(Order, order_id)
            order.created_at = old + timedelta(microseconds=offset)
            deferred_provider_ids.add(provider_order_id)
        target_id, target_provider_id, _ = _old_unpaid_order(db)
        db.get(Order, target_id).created_at = old + timedelta(minutes=1)
        db.commit()

        calls = []

        def provider_history(*, provider_order_id):
            calls.append(provider_order_id)
            if provider_order_id in deferred_provider_ids:
                raise PaymentProviderUnavailable("simulated provider outage")
            return []

        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments", provider_history,
        )
        for _ in range(2):
            payment_expiration.expire_unpaid_orders(db, limit=1)

        assert target_provider_id in calls
        assert db.get(Order, target_id).status == OrderStatus.CANCELLED
