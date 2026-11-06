"""UPI expiration must fail closed when a legacy order has no provider intent."""
from datetime import datetime, timedelta, timezone

from app.models.commerce import StoreProduct
from app.models.orders import Order, OrderItem, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import make_order, session


def test_missing_payment_attempt_does_not_expire_or_restore_reserved_stock(monkeypatch):
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False)
        order.created_at = datetime.now(timezone.utc) - timedelta(minutes=40)
        item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
        listing = db.query(StoreProduct).filter(
            StoreProduct.store_id == order.store_id,
            StoreProduct.product_id == item.product_id,
        ).one()
        listing.stock_quantity -= item.quantity
        order_id, listing_id = order.id, listing.id
        db.commit()

        def unexpected_provider_lookup(**kwargs):
            raise AssertionError("No provider order exists to reconcile")

        monkeypatch.setattr(payment_expiration, "list_razorpay_order_payments", unexpected_provider_lookup)
        result = payment_expiration.expire_unpaid_orders(db, limit=10)
        assert result["deferred"] >= 1
        assert result["expired"] == 0
        db.expire_all()
        current = db.get(Order, order_id)
        assert current.status == OrderStatus.PLACED
        assert current.payment_status == PaymentStatus.PENDING
        assert current.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
