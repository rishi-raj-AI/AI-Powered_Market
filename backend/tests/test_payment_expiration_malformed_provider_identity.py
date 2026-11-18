"""Malformed Razorpay payment identities must never authorize UPI expiry or capture."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.commerce import StoreProduct
from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderItem, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import make_order, session


@pytest.mark.parametrize("payment_id", [" ", "pay_123 ", " pay_123", "\t"])
@pytest.mark.parametrize("provider_status", ["failed", "captured"])
def test_expiry_quarantines_malformed_provider_payment_identity(
    monkeypatch, payment_id, provider_status,
):
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False)
        order.created_at = datetime.now(timezone.utc) - timedelta(minutes=40)
        provider_order_id = f"order_{uuid4().hex}"
        db.add(PaymentAttempt(
            order_id=order.id, provider="razorpay", provider_order_id=provider_order_id,
            status="attempted", amount=Decimal("120.00"), currency="INR",
        ))
        item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
        listing = db.query(StoreProduct).filter(
            StoreProduct.store_id == order.store_id,
            StoreProduct.product_id == item.product_id,
        ).one()
        listing.stock_quantity -= item.quantity
        db.commit()
        order_id, listing_id = order.id, listing.id

        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": payment_id, "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": provider_status,
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        assert db.get(Order, order_id).status == OrderStatus.PLACED
        assert db.get(Order, order_id).payment_status == PaymentStatus.PENDING
        assert db.get(Order, order_id).stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
