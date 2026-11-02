"""A stale local order cannot open another Razorpay intent.

Disposable PostgreSQL records and mocked provider calls only.
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import payments as payment_routes
from app.models.integrations import PaymentAttempt
from app.models.orders import OrderStatus, PaymentStatus
from tests.factories import make_order, make_user, session


def _context(db):
    customer = make_user(db)
    order = make_order(
        db, customer=customer, payment_status=PaymentStatus.PENDING,
        with_paid_attempt=False,
    )
    attempt = PaymentAttempt(
        order_id=order.id,
        provider="razorpay",
        provider_order_id=f"order_{uuid4().hex}",
        status="attempted",
        amount=Decimal("120.00"),
        currency="INR",
    )
    db.add(attempt)
    db.commit()
    return customer, order, attempt


@pytest.mark.parametrize("evidence", ["paid_status", "payment_id"])
def test_intent_refuses_stale_order_with_existing_capture(monkeypatch, evidence):
    with session() as db:
        customer, order, attempt = _context(db)
        if evidence == "paid_status":
            attempt.status = "paid"
        else:
            attempt.provider_payment_id = f"pay_{uuid4().hex}"
        db.commit()
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_: pytest.fail("A captured attempt must block a new provider order"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409
        assert "reconciliation" in exc.value.detail
        db.refresh(attempt)
        assert attempt.provider_order_id is not None


@pytest.mark.parametrize("invalid_field", ["amount", "currency"])
def test_intent_refuses_stale_provider_order_terms(monkeypatch, invalid_field):
    with session() as db:
        customer, order, attempt = _context(db)
        if invalid_field == "amount":
            attempt.amount = Decimal("119.00")
        else:
            attempt.currency = "USD"
        db.commit()
        monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_mock")
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_: pytest.fail("Must not create another intent for stale terms"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409
        assert "reconciliation" in exc.value.detail
        db.refresh(attempt)
        assert attempt.status == "attempted"


@pytest.mark.parametrize("state", [
    PaymentStatus.PAID, PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED,
])
def test_intent_refuses_nonpayable_order_payment_states(monkeypatch, state):
    with session() as db:
        customer, order, _attempt = _context(db)
        order.payment_status = state
        db.commit()
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_: pytest.fail("Nonpayable order must not call provider"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409


def test_intent_refuses_nonplaced_order_even_if_payment_pending(monkeypatch):
    with session() as db:
        customer, order, _attempt = _context(db)
        order.status = OrderStatus.CONFIRMED
        db.commit()
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_: pytest.fail("Nonplaced order must not call provider"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409
