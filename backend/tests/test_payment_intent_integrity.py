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
        order.status = OrderStatus.ACCEPTED
        db.commit()
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_: pytest.fail("Nonplaced order must not call provider"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409


def _provider_payment(attempt, *, status="failed", **overrides):
    payment = {
        "id": f"pay_{uuid4().hex}",
        "order_id": attempt.provider_order_id,
        "status": status,
        "amount": 12000,
        "currency": "INR",
    }
    payment.update(overrides)
    return payment


@pytest.mark.parametrize("history_kind", [
    "captured", "authorized", "created", "refunded", "unknown",
    "failed_wrong_order", "failed_wrong_amount", "failed_wrong_currency",
    "failed_missing_id",
])
def test_intent_retry_never_exposes_unsettled_or_malformed_provider_history(
    monkeypatch, history_kind,
):
    with session() as db:
        customer, order, attempt = _context(db)
        monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_mock")
        if history_kind.startswith("failed_"):
            overrides = {
                "failed_wrong_order": {"order_id": "order_other"},
                "failed_wrong_amount": {"amount": 11999},
                "failed_wrong_currency": {"currency": "USD"},
                "failed_missing_id": {"id": ""},
            }[history_kind]
            payment = _provider_payment(attempt, **overrides)
        else:
            payment = _provider_payment(attempt, status=history_kind)
        monkeypatch.setattr(
            payment_routes, "list_razorpay_order_payments",
            lambda **_kwargs: [payment],
        )
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail("Must not create another provider order"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409
        assert "reconciliation" in exc.value.detail
        db.refresh(attempt)
        assert attempt.status == "attempted"


@pytest.mark.parametrize("with_failed_retry", [False, True])
def test_intent_retry_allows_only_empty_or_terminal_failed_provider_history(
    monkeypatch, with_failed_retry,
):
    with session() as db:
        customer, order, attempt = _context(db)
        monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_mock")
        history = [_provider_payment(attempt)] if with_failed_retry else []
        monkeypatch.setattr(
            payment_routes, "list_razorpay_order_payments",
            lambda **_kwargs: history,
        )
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail("Existing intent must be reused"),
        )
        response = payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert response.provider_order_id == attempt.provider_order_id
        assert response.payment_attempt_id == attempt.id


@pytest.mark.parametrize("provider_exception, expected_status", [
    ("unavailable", 503),
    ("error", 502),
])
def test_intent_retry_defers_on_provider_read_failure(
    monkeypatch, provider_exception, expected_status,
):
    from app.services.payments import PaymentProviderError, PaymentProviderUnavailable

    with session() as db:
        customer, order, attempt = _context(db)
        monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_mock")
        error_type = (
            PaymentProviderUnavailable if provider_exception == "unavailable"
            else PaymentProviderError
        )

        def failed_lookup(**_kwargs):
            raise error_type("mock provider outage")

        monkeypatch.setattr(payment_routes, "list_razorpay_order_payments", failed_lookup)
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail("Provider outage must not create a new intent"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == expected_status
        db.refresh(attempt)
        assert attempt.status == "attempted"


def test_intent_reuse_rejects_capture_on_older_failed_provider_order(monkeypatch):
    """A newer active intent cannot hide captured money on an older failed attempt."""
    with session() as db:
        customer, order, active = _context(db)
        older_provider_order_id = f"order_older_{uuid4().hex}"
        older = PaymentAttempt(
            order_id=order.id,
            provider="razorpay",
            provider_order_id=older_provider_order_id,
            status="failed",
            amount=order.total,
            currency="INR",
        )
        db.add(older)
        db.commit()
        monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_mock")
        queried = []

        def history(*, provider_order_id):
            queried.append(provider_order_id)
            if provider_order_id == older_provider_order_id:
                return [{
                    "id": f"pay_late_{uuid4().hex}",
                    "order_id": older_provider_order_id,
                    "status": "captured",
                    "amount": 12000,
                    "currency": "INR",
                }]
            return []

        monkeypatch.setattr(payment_routes, "list_razorpay_order_payments", history)
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail("Older captured payment must block new intent"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409
        assert older_provider_order_id in queried
        db.refresh(active)
        assert active.status == "attempted"
