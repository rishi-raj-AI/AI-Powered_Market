"""A captured provider payment already assigned to another order is ambiguous.

Uses disposable database rows and mocked Razorpay history only.
"""
from uuid import uuid4

from app.models.commerce import StoreProduct
from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.services import payment_expiration
from tests.factories import make_order, session
from tests.test_payment_expiration import _old_unpaid_order


def test_capture_owned_by_other_order_never_confirms_or_releases_stock(monkeypatch):
    with session() as db:
        order_id, provider_order_id, listing_id = _old_unpaid_order(db)
        other = make_order(db, payment_status=PaymentStatus.PAID, with_paid_attempt=False)
        payment_id = f"pay_{uuid4().hex}"
        db.add(PaymentAttempt(
            order_id=other.id,
            provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            provider_payment_id=payment_id,
            status="paid",
            amount=other.total,
            currency="INR",
        ))
        db.commit()

        monkeypatch.setattr(
            payment_expiration,
            "list_razorpay_order_payments",
            lambda **_: [{
                "id": payment_id,
                "order_id": provider_order_id,
                "amount": 12000,
                "currency": "INR",
                "status": "captured",
            }],
        )
        result = payment_expiration.expire_unpaid_orders(db, limit=1)
        db.expire_all()
        order = db.get(Order, order_id)
        assert result["captured"] == 0
        assert result["expired"] == 0
        assert result["deferred"] >= 1
        assert order.status == OrderStatus.PLACED
        assert order.payment_status == PaymentStatus.PENDING
        assert order.stock_restored_at is None
        assert db.get(StoreProduct, listing_id).stock_quantity == 9
