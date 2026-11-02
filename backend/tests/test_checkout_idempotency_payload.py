"""Idempotent checkout retries must not silently change address or payment intent.

Synthetic PostgreSQL integration tests. No Razorpay calls or production writes.
The second-read cases model an order committed by a competing request while
the retry waits on the customer's cart lock.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.v1.routes import checkout
from app.models.geography import Address, Village
from app.models.orders import Cart, Order, PaymentMethod, PaymentStatus
from app.schemas.orders import CheckoutRequest
from tests import factories


@pytest.mark.parametrize("phase", ["first_read", "after_cart_lock"])
@pytest.mark.parametrize("changed_field", ["none", "address", "payment_method"])
def test_idempotent_replay_matches_original_address_and_payment(
    monkeypatch, phase, changed_field,
):
    with factories.session() as db:
        customer = factories.make_user(db)
        store = factories.make_store(db, is_active=True)
        order = factories.make_order(
            db,
            customer=customer,
            store=store,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        key = f"replay-{uuid4()}"
        order.idempotency_key = key
        original_address = db.get(Address, order.address_id)
        assert original_address is not None
        other_address = factories.make_address(
            db, customer, db.get(Village, store.village_id),
        )
        db.add(Cart(user_id=customer.id, store_id=store.id))
        db.flush()

        payload = CheckoutRequest(
            address_id=other_address.id if changed_field == "address" else order.address_id,
            payment_method=(
                PaymentMethod.UPI if changed_field == "payment_method"
                else PaymentMethod.COD
            ),
        )
        before = db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id))

        if phase == "after_cart_lock":
            # Simulate the race: first read saw no order, second read after
            # locking the cart sees the committed winner's order.
            reads = iter([None, order])
            monkeypatch.setattr(
                checkout, "_existing_idempotent_order",
                lambda *_args: next(reads),
            )

        if changed_field == "none":
            replay = checkout.safe_checkout(
                payload, idempotency_key=key, db=db, user=customer,
            )
            assert replay.id == order.id
        else:
            with pytest.raises(HTTPException) as error:
                checkout.safe_checkout(
                    payload, idempotency_key=key, db=db, user=customer,
                )
            assert error.value.status_code == 409
            assert "Idempotency-Key" in error.value.detail

        assert db.scalar(select(func.count(Order.id)).where(Order.user_id == customer.id)) == before
        db.rollback()


def test_same_checkout_retry_can_return_original_order_after_address_archived():
    with factories.session() as db:
        customer = factories.make_user(db)
        order = factories.make_order(
            db, customer=customer, payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PENDING, with_paid_attempt=False,
        )
        order.idempotency_key = f"archived-{uuid4()}"
        address = db.get(Address, order.address_id)
        address.archived_at = datetime.now(timezone.utc)
        db.flush()

        result = checkout.safe_checkout(
            CheckoutRequest(address_id=order.address_id, payment_method=PaymentMethod.COD),
            idempotency_key=order.idempotency_key, db=db, user=customer,
        )
        assert result.id == order.id
        db.rollback()
