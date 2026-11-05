"""Never release UPI stock while Razorpay reports an unsettled money movement.

All provider reads are mocked. These tests use disposable local database fixtures
and do not contact Razorpay or mutate live financial records.
"""
import pytest

from app.models.commerce import StoreProduct
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import session
from tests.test_payment_expiration import _old_unpaid_order


@pytest.mark.parametrize("provider_status", ["authorized", "created", "refunded", "processing", None])
def test_nonterminal_or_ambiguous_provider_payment_preserves_reservation(
    monkeypatch, provider_status,
):
    """Only verified capture or reliably empty/failed history permits a transition."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration,
            "list_razorpay_order_payments",
            lambda **_: [{
                "id": "pay_ambiguous123",
                "order_id": provider_order_id,
                "amount": 12000,
                "currency": "INR",
                "status": provider_status,
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        db.expire_all()
        order = db.get(Order, order_id)
        assert result["expired"] == 0
        assert result["captured"] == 0
        assert result["deferred"] >= 1
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9


@pytest.mark.parametrize("invalid_amount", [True, None, "12000", 12001])
def test_ambiguous_failed_payment_amount_cannot_authorize_stock_release(
    monkeypatch, invalid_amount,
):
    """A provider 'failed' label alone does not establish a trustworthy money amount."""
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration,
            "list_razorpay_order_payments",
            lambda **_: [{
                "id": "pay_failed123",
                "order_id": provider_order_id,
                "amount": invalid_amount,
                "currency": "INR",
                "status": "failed",
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        db.expire_all()
        order = db.get(Order, order_id)
        assert result["expired"] == 0
        assert result["captured"] == 0
        assert result["deferred"] >= 1
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
