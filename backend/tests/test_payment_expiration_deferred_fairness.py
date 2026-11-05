"""Expiration must keep scanning after provider uncertainty on an older order.

Disposable fixtures and mocked provider responses only; no live payment calls.
"""
from datetime import datetime, timedelta, timezone

from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from app.services.payments import PaymentProviderUnavailable
from tests.factories import session
from tests.test_payment_expiration import _old_unpaid_order


def _two_old_orders(db):
    first_id, first_provider_order, first_listing = _old_unpaid_order(db)
    second_id, second_provider_order, second_listing = _old_unpaid_order(db)
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    db.get(Order, first_id).created_at = old
    db.get(Order, second_id).created_at = old + timedelta(seconds=1)
    db.commit()
    return first_id, first_provider_order, first_listing, second_id, second_provider_order, second_listing


def test_provider_outage_defers_older_order_but_expires_later_safe_order(monkeypatch):
    with session() as db:
        first_id, first_provider, _, second_id, second_provider, _ = _two_old_orders(db)
        calls = []

        def history(*, provider_order_id):
            calls.append(provider_order_id)
            if provider_order_id == first_provider:
                raise PaymentProviderUnavailable("mock provider outage")
            assert provider_order_id == second_provider
            return []

        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", history)
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        assert result["deferred"] >= 1
        assert result["expired"] == 1
        assert calls == [first_provider, second_provider]
        first = db.get(Order, first_id)
        second = db.get(Order, second_id)
        assert first.status == OrderStatus.PLACED
        assert first.payment_status == PaymentStatus.PENDING
        assert first.stock_restored_at is None
        assert second.status == OrderStatus.CANCELLED


def test_ambiguous_capture_defers_older_order_but_does_not_starve_later_order(monkeypatch):
    with session() as db:
        first_id, first_provider, _, second_id, second_provider, _ = _two_old_orders(db)
        calls = []

        def history(*, provider_order_id):
            calls.append(provider_order_id)
            if provider_order_id == first_provider:
                return [{
                    "id": "pay_ambiguous_amount", "order_id": first_provider,
                    "status": "captured", "amount": 1, "currency": "INR",
                }]
            assert provider_order_id == second_provider
            return []

        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", history)
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        assert result["deferred"] >= 1
        assert result["captured"] == 0
        assert result["expired"] == 1
        assert calls == [first_provider, second_provider]
        first = db.get(Order, first_id)
        assert first.status == OrderStatus.PLACED
        assert first.payment_status == PaymentStatus.PENDING
        assert first.stock_restored_at is None
        assert db.get(Order, second_id).status == OrderStatus.CANCELLED
