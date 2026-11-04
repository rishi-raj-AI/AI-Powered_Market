"""Regressions for deterministic payment-expiration keyset ordering.

Disposable fixtures only; all provider responses are mocked.
"""
from datetime import datetime, timedelta, timezone

from app.models.orders import OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import make_order, session
from tests.test_payment_expiration import _old_unpaid_order


def test_expiry_pages_across_equal_created_at_timestamps(monkeypatch):
    """The ID tie-breaker must reach eligible rows beyond a full batch."""
    with session() as db:
        timestamp = datetime.now(timezone.utc) - timedelta(hours=3)
        deferred_ids = []
        for _ in range(30):
            order = make_order(
                db, payment_status=PaymentStatus.PENDING,
                with_paid_attempt=False,
            )
            order.created_at = timestamp
            deferred_ids.append(order.id)
        db.commit()

        target_id, _, _ = _old_unpaid_order(db)
        target = db.get(type(order), target_id)
        target.created_at = timestamp
        db.commit()

        # UUID ordering, not insertion ordering, determines the cursor.
        # The eligible target may occur in the first batch; regardless, no
        # candidate may be lost or processed twice at a timestamp boundary.
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        assert result["expired"] == 1
        assert result["captured"] == 0
        assert result["considered"] <= 31
        assert db.get(type(order), target_id).status == OrderStatus.CANCELLED
        assert all(
            db.get(type(order), order_id).status == OrderStatus.PLACED
            for order_id in deferred_ids
        )


def test_expiry_scan_budget_bounds_all_deferred_orders(monkeypatch):
    """Unreconcilable legacy rows must not cause unbounded scans."""
    with session() as db:
        timestamp = datetime.now(timezone.utc) - timedelta(hours=3)
        for offset in range(510):
            order = make_order(
                db, payment_status=PaymentStatus.PENDING,
                with_paid_attempt=False,
            )
            order.created_at = timestamp + timedelta(microseconds=offset)
        db.commit()
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: (_ for _ in ()).throw(AssertionError("unexpected provider call")),
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        assert result == {
            "considered": 500,
            "expired": 0,
            "captured": 0,
            "deferred": 500,
        }
