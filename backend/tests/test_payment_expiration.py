"""Opt-in UPI reservation expiration must never assume provider failure."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.models.commerce import StoreProduct
from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderItem, OrderStatus, PaymentStatus
from app.services import payment_expiration
from app.services.payments import PaymentProviderUnavailable
from tests.factories import make_order, session


def _old_unpaid_order(db):
    order = make_order(db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False)
    order.created_at = datetime.now(timezone.utc) - timedelta(minutes=40)
    attempt = PaymentAttempt(
        order_id=order.id, provider="razorpay",
        provider_order_id=f"order_{uuid4().hex}", status="attempted",
        amount=Decimal("120.00"), currency="INR",
    )
    db.add(attempt)
    item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
    listing = db.query(StoreProduct).filter(
        StoreProduct.store_id == order.store_id,
        StoreProduct.product_id == item.product_id,
    ).one()
    listing.stock_quantity -= item.quantity  # model the checkout reservation
    db.commit()
    return order.id, attempt.provider_order_id, listing.id


def test_expired_unpaid_upi_order_restores_stock_exactly_once(monkeypatch):
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", lambda **_: [])
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["expired"] >= 1
        order = db.get(Order, order_id)
        listing = db.get(StoreProduct, listing_id)
        assert order.status == OrderStatus.CANCELLED
        assert order.stock_restored_at is not None
        assert listing.stock_quantity == 10
        again = payment_expiration.expire_unpaid_orders(db, limit=10)
        db.refresh(listing)
        assert again["expired"] == 0
        assert listing.stock_quantity == 10


def test_expiry_reconciles_captured_payment_instead_of_cancelling(monkeypatch):
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": "captured",
            }],
        )
        monkeypatch.setattr(payment_expiration, "_notify_payment_captured", lambda *_: None)
        monkeypatch.setattr(payment_expiration, "_apply_paid", lambda _db, attempt, order, payment_id: (
            setattr(attempt, "status", "paid"),
            setattr(attempt, "provider_payment_id", payment_id),
            setattr(order, "payment_status", PaymentStatus.PAID),
        ))
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["captured"] >= 1
        order = db.get(Order, order_id)
        listing = db.get(StoreProduct, listing_id)
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PAID
        assert listing.stock_quantity == 9


def test_provider_outage_defers_expiration_and_preserves_stock(monkeypatch):
    with session() as db:
        order_id, _provider_order_id, listing_id = _old_unpaid_order(db)

        def unavailable(**_kwargs):
            raise PaymentProviderUnavailable("test provider outage")

        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", unavailable)
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        order = db.get(Order, order_id)
        listing = db.get(StoreProduct, listing_id)
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert listing.stock_quantity == 9


def test_authorized_payment_is_not_expired(monkeypatch):
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        monkeypatch.setattr(
            payment_expiration, "list_razorpay_order_payments",
            lambda **_: [{
                "id": f"pay_{uuid4().hex}", "order_id": provider_order_id,
                "amount": 12000, "currency": "INR", "status": "authorized",
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        assert db.get(Order, order_id).status == OrderStatus.PLACED
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
