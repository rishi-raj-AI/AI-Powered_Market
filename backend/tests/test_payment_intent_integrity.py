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


@pytest.mark.parametrize("provider_status", [
    "captured", "authorized", "created", "refunded", "unknown",
])
def test_failed_local_attempt_cannot_be_replaced_with_unsettled_provider_money(
    monkeypatch, provider_status,
):
    with session() as db:
        customer, order, attempt = _context(db)
        attempt.status = "failed"
        db.commit()
        monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_mock")
        monkeypatch.setattr(
            payment_routes, "list_razorpay_order_payments",
            lambda **_kwargs: [_provider_payment(attempt, status=provider_status)],
        )
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail("Historical provider money must block new intents"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409
        db.refresh(attempt)
        assert attempt.status == "failed"


def test_new_intent_allowed_after_provider_confirms_only_failed_previous_payment(
    monkeypatch,
):
    with session() as db:
        customer, order, attempt = _context(db)
        attempt.status = "failed"
        db.commit()
        monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_mock")
        monkeypatch.setattr(
            payment_routes, "list_razorpay_order_payments",
            lambda **_kwargs: [_provider_payment(attempt)],
        )
        created = []
        def mock_create(**kwargs):
            created.append(kwargs)
            return {"id": f"order_new_{uuid4().hex}"}
        monkeypatch.setattr(payment_routes, "create_razorpay_order", mock_create)
        response = payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert response.provider_order_id.startswith("order_new_")
        assert response.payment_attempt_id != attempt.id
        assert len(created) == 1


def test_older_unsettled_attempt_blocks_reusing_newer_active_intent(monkeypatch):
    with session() as db:
        customer, order, older = _context(db)
        older.status = "failed"
        newer = PaymentAttempt(
            order_id=order.id, provider="razorpay",
            provider_order_id=f"order_{uuid4().hex}",
            status="attempted", amount=order.total, currency="INR",
        )
        db.add(newer)
        db.commit()
        monkeypatch.setattr(payment_routes.settings, "RAZORPAY_KEY_ID", "rzp_test_mock")

        def lookup(*, provider_order_id):
            if provider_order_id == older.provider_order_id:
                return [_provider_payment(older, status="captured")]
            return []

        monkeypatch.setattr(payment_routes, "list_razorpay_order_payments", lookup)
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail("Cannot bypass an older captured payment"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409


@pytest.mark.parametrize("scenario", ["two_active", "active_without_provider_order"])
def test_ambiguous_active_intent_history_requires_reconciliation(monkeypatch, scenario):
    """An empty provider history cannot prove a second live checkout is safe."""
    with session() as db:
        customer, order, attempt = _context(db)
        if scenario == "two_active":
            db.add(PaymentAttempt(
                order_id=order.id,
                provider="razorpay",
                provider_order_id=f"order_{uuid4().hex}",
                status="created",
                amount=order.total,
                currency="INR",
            ))
        else:
            attempt.provider_order_id = None
        db.commit()
        monkeypatch.setattr(
            payment_routes, "list_razorpay_order_payments",
            lambda **_kwargs: pytest.fail("Ambiguous active intents must fail before provider reads"),
        )
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail("Must not create another provider order"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409
        assert "reconciliation" in exc.value.detail


def test_unknown_historical_payment_provider_blocks_new_intent(monkeypatch):
    with session() as db:
        customer, order, attempt = _context(db)
        attempt.provider = "unrecognized"
        attempt.status = "failed"
        db.commit()
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail("Unknown provider must not be ignored"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409


@pytest.mark.parametrize("local_status", ["authorized", "processing", "refunded", "unknown"])
def test_unrecognized_local_attempt_state_cannot_open_another_intent(
    monkeypatch, local_status,
):
    with session() as db:
        customer, order, attempt = _context(db)
        attempt.status = local_status
        db.commit()
        monkeypatch.setattr(
            payment_routes, "list_razorpay_order_payments",
            lambda **_kwargs: pytest.fail("Unsafe local state must fail before provider read"),
        )
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail("Unsafe local state must not create another intent"),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409


@pytest.mark.parametrize("ordering", ["alone", "unidentified_first", "unidentified_last"])
def test_failed_attempt_without_provider_order_id_blocks_checkout(
    monkeypatch, ordering,
):
    """All local attempts must pass preflight before any provider-history lookup."""
    with session() as db:
        customer, order, attempt = _context(db)
        attempt.status = "failed"
        attempt.provider_order_id = None
        if ordering != "alone":
            # Force both UUID iteration orders to make the regression
            # deterministic rather than relying on random generated IDs.
            other_id = uuid4()
            while (other_id > attempt.id) != (ordering == "unidentified_first"):
                other_id = uuid4()
            db.add(PaymentAttempt(
                id=other_id,
                order_id=order.id,
                provider="razorpay",
                provider_order_id=f"order_{uuid4().hex}",
                status="attempted",
                amount=order.total,
                currency="INR",
            ))
        db.commit()

        monkeypatch.setattr(
            payment_routes, "list_razorpay_order_payments",
            lambda **_kwargs: pytest.fail(
                "An unidentified historical attempt must block before provider reads"
            ),
        )
        monkeypatch.setattr(
            payment_routes, "create_razorpay_order",
            lambda **_kwargs: pytest.fail(
                "An unidentified historical attempt must not open a new checkout"
            ),
        )
        with pytest.raises(HTTPException) as exc:
            payment_routes.create_payment_intent(order.id, db=db, user=customer)
        assert exc.value.status_code == 409
        assert "reconciliation" in exc.value.detail
        db.refresh(attempt)
        assert attempt.status == "failed"
        assert attempt.provider_order_id is None
