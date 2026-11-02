"""P0-A: a cancelled paid order must actually return the customer's money.

Before this change the backend wrote ``payment_status = refunded`` and made no
provider call at all. These tests pin the properties that make that impossible
to reintroduce.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import event

from app.api.v1.routes.payment_hardening import _process_refund_event
from app.models.integrations import PaymentRefund
from app.models.orders import OrderStatus, PaymentMethod, PaymentStatus
from app.services import payments as payment_service
from app.services import refunds as refund_service
from app.services.refunds import (
    REFUND_FAILED,
    REFUND_PROCESSING,
    REFUND_REASON_CANCELLED,
    REFUND_SUCCEEDED,
    dispatch_due_refunds,
    dispatch_refund,
    ensure_refund_request,
    get_refund_for_order,
)
from tests.factories import make_order, session


def test_provider_refund_uses_razorpay_refund_idempotency_contract(monkeypatch) -> None:
    captured: dict = {}

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, *, auth, headers, json):
            captured.update(url=url, auth=auth, headers=headers, json=json)
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={"id": "rfnd_provider", "status": "processed"},
            )

    monkeypatch.setattr(payment_service.httpx, "Client", Client)
    monkeypatch.setattr(payment_service.settings, "RAZORPAY_KEY_ID", "rzp_test_example")
    monkeypatch.setattr(payment_service.settings, "RAZORPAY_KEY_SECRET", "test-secret")

    payload = payment_service.create_razorpay_refund(
        provider_payment_id="pay_provider",
        amount=Decimal("55.00"),
        idempotency_key="order-refund:0a1bd26c-d2cd-4ab9-8926-a571cb038cb5",
        notes={"gaonone_order_id": "0a1bd26c-d2cd-4ab9-8926-a571cb038cb5"},
    )

    assert payload["id"] == "rfnd_provider"
    assert captured["headers"] == {
        "X-Refund-Idempotency": "order-refund-0a1bd26c-d2cd-4ab9-8926-a571cb038cb5"
    }
    assert ":" not in captured["headers"]["X-Refund-Idempotency"]


def _rid(label: str) -> str:
    """Provider ids are globally unique; the test database persists between runs."""
    return f"{label}_{uuid4().hex[:12]}"


class _ProviderSpy:
    def __init__(self, result=None, error=None):
        self.calls: list[dict] = []
        self._result = result
        self._error = error

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        if isinstance(self._result, dict):
            # Real Razorpay refund responses identify the payment, amount and
            # currency. Supply those fields in normal provider fixtures.
            payload = dict(self._result)
            payload.setdefault("payment_id", kwargs["provider_payment_id"])
            payload.setdefault("amount", payment_service.amount_to_subunits(kwargs["amount"]))
            payload.setdefault("currency", "INR")
            return payload
        return self._result


def _enable_provider(monkeypatch) -> None:
    monkeypatch.setattr(refund_service, "razorpay_enabled", lambda: True)


def test_cancelling_paid_upi_order_records_refund_and_never_claims_refunded() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()

        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert refund is not None
        assert refund.status == "requested"
        assert refund.amount == order.total
        assert refund.reason == REFUND_REASON_CANCELLED
        # The customer is owed money; nothing may claim it has been returned.
        assert order.payment_status == PaymentStatus.REFUND_PENDING


def test_duplicate_cancellation_does_not_create_a_second_refund() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()

        first = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        second = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert first is not None and second is not None
        assert first.id == second.id
        count = (
            db.query(PaymentRefund).filter(PaymentRefund.order_id == order.id).count()
        )
        assert count == 1


def test_cod_order_never_creates_a_provider_refund() -> None:
    with session() as db:
        order = make_order(
            db,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PAID,
            with_paid_attempt=False,
        )
        db.commit()

        assert ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED) is None
        assert get_refund_for_order(db, order.id) is None
        assert order.payment_status == PaymentStatus.PAID


def test_cancellation_before_payment_owes_nothing() -> None:
    with session() as db:
        order = make_order(
            db,
            payment_status=PaymentStatus.PENDING,
            with_paid_attempt=False,
        )
        db.commit()

        assert ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED) is None
        assert get_refund_for_order(db, order.id) is None


def test_successful_provider_refund_marks_order_refunded_once(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    provider_refund_id = _rid("rfnd_success")
    spy = _ProviderSpy(result={"id": provider_refund_id, "status": "processed"})
    monkeypatch.setattr(refund_service, "create_razorpay_refund", spy)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        refund_id = refund.id

        assert dispatch_refund(db, refund_id) == REFUND_SUCCEEDED
        assert len(spy.calls) == 1

        # A second dispatch is a no-op: the provider must not be called twice.
        assert dispatch_refund(db, refund_id) == REFUND_SUCCEEDED
        assert len(spy.calls) == 1

        db.refresh(refund)
        db.refresh(order)
        assert refund.provider_refund_id == provider_refund_id
        assert refund.processed_at is not None
        assert order.payment_status == PaymentStatus.REFUNDED


def test_provider_failure_leaves_a_recoverable_obligation(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    boom = _ProviderSpy(error=refund_service.PaymentProviderError("Unable to reach Razorpay"))
    monkeypatch.setattr(refund_service, "create_razorpay_refund", boom)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert dispatch_refund(db, refund.id) == REFUND_FAILED
        db.refresh(refund)
        db.refresh(order)

        assert refund.attempt_count == 1
        assert refund.failure_reason
        assert refund.failed_at is not None
        # Critically: a provider outage must never look like a completed refund.
        assert order.payment_status == PaymentStatus.REFUND_PENDING
        # And the obligation stays visible to the retry worker.
        assert refund.id in refund_service.due_refund_ids(db, order_id=order.id)


def test_failed_refund_is_retried_and_can_succeed(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    boom = _ProviderSpy(error=refund_service.PaymentProviderError("network"))
    monkeypatch.setattr(refund_service, "create_razorpay_refund", boom)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        dispatch_refund(db, refund.id)

        ok = _ProviderSpy(result={"id": _rid("rfnd_retry_1"), "status": "processed"})
        monkeypatch.setattr(refund_service, "create_razorpay_refund", ok)
        outcome = dispatch_due_refunds(db, order_id=order.id)

        assert outcome["succeeded"] == 1
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUNDED


@pytest.mark.parametrize("incorrect", [
    {"payment_id": "pay_other_transaction"},
    {"amount": 1},
    {"currency": "USD"},
    {"id": ""},
])
def test_refund_dispatch_quarantines_mismatched_provider_response(monkeypatch, incorrect) -> None:
    """A provider HTTP 200 must not become a false customer refund."""
    _enable_provider(monkeypatch)
    payload = {"id": _rid("rfnd_mismatch"), "status": "processed", **incorrect}
    monkeypatch.setattr(refund_service, "create_razorpay_refund", _ProviderSpy(result=payload))

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert dispatch_refund(db, refund.id) == REFUND_PROCESSING
        db.refresh(refund)
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUND_PENDING
        assert refund.status == REFUND_PROCESSING
        assert refund.provider_refund_id is None
        assert "reconciliation" in refund.failure_reason
        assert refund.id not in refund_service.due_refund_ids(db, order_id=order.id)


def test_refund_dispatch_quarantines_incomplete_provider_response(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    # A truncated response cannot prove that the payment and amount match.
    monkeypatch.setattr(
        refund_service, "create_razorpay_refund",
        lambda **_kwargs: {"id": _rid("rfnd_incomplete"), "status": "processed"},
    )
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        assert dispatch_refund(db, refund.id) == REFUND_PROCESSING
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUND_PENDING


def test_pending_provider_refund_waits_for_confirmation(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    provider_refund_id = _rid("rfnd_pending")
    spy = _ProviderSpy(result={"id": provider_refund_id, "status": "pending"})
    monkeypatch.setattr(refund_service, "create_razorpay_refund", spy)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert dispatch_refund(db, refund.id) == REFUND_PROCESSING
        db.refresh(order)
        # Provider accepted but has not settled: still not "refunded".
        assert order.payment_status == PaymentStatus.REFUND_PENDING

        # The later webhook is what completes it.
        refund_service.apply_provider_refund_result(
            db, refund, {"id": provider_refund_id, "status": "processed"}
        )
        db.commit()
        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUNDED


def test_refund_without_captured_payment_id_is_flagged_for_reconciliation(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    spy = _ProviderSpy(result={"id": _rid("rfnd_never"), "status": "processed"})
    monkeypatch.setattr(refund_service, "create_razorpay_refund", spy)

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID, with_paid_attempt=False)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert refund is not None and refund.provider_payment_id is None
        assert dispatch_refund(db, refund.id) == REFUND_FAILED
        assert spy.calls == []
        db.refresh(refund)
        assert "manual reconciliation" in (refund.failure_reason or "")


def test_terminal_refunded_order_stays_refunded_on_repeat_webhook(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    provider_refund_id = _rid("rfnd_terminal")
    monkeypatch.setattr(
        refund_service,
        "create_razorpay_refund",
        _ProviderSpy(result={"id": provider_refund_id, "status": "processed"}),
    )

    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        dispatch_refund(db, refund.id)

        for _ in range(3):
            refund_service.apply_provider_refund_result(
                db, refund, {"id": provider_refund_id, "status": "processed"}
            )
            db.commit()

        db.refresh(order)
        assert order.payment_status == PaymentStatus.REFUNDED
        assert (
            db.query(PaymentRefund).filter(PaymentRefund.order_id == order.id).count() == 1
        )


def test_refund_amount_matches_order_total_exactly() -> None:
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID, total=Decimal("437.50"))
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        assert refund is not None
        assert Decimal(refund.amount) == Decimal("437.50")


@pytest.mark.parametrize(
    "order_status",
    [OrderStatus.PLACED, OrderStatus.ACCEPTED, OrderStatus.CANCELLED],
)
def test_refund_obligation_is_independent_of_order_status(order_status) -> None:
    with session() as db:
        order = make_order(db, status=order_status, payment_status=PaymentStatus.PAID)
        db.commit()
        assert ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED) is not None


def test_unknown_refund_webhook_cannot_guess_between_multiple_obligations() -> None:
    """A shared provider payment ID is insufficient to identify a refund row."""
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        first = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        assert first is not None and first.provider_payment_id
        second = PaymentRefund(
            order_id=order.id,
            payment_attempt_id=first.payment_attempt_id,
            provider="razorpay",
            provider_payment_id=first.provider_payment_id,
            amount=first.amount,
            currency=first.currency,
            status="requested",
            reason="duplicate_capture_review",
            idempotency_key=f"test-ambiguous-refund-{uuid4()}",
            requested_at=datetime.now(timezone.utc),
        )
        db.add(second)
        db.commit()

        handled = _process_refund_event(db, {
            "event": "refund.processed",
            "payload": {"refund": {"entity": {
                "id": f"rfnd_{uuid4().hex}",
                "payment_id": first.provider_payment_id,
                "amount": 12000, "currency": "INR", "status": "processed",
            }}},
        })
        assert handled is False
        db.refresh(first)
        db.refresh(second)
        assert first.provider_refund_id is None
        assert second.provider_refund_id is None
        assert first.status == "requested"
        assert second.status == "requested"


def test_refund_webhook_can_resolve_single_unbound_obligation() -> None:
    """Fallback matching is safe only when exactly one candidate exists."""
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        assert refund is not None and refund.provider_payment_id
        assert refund.provider_refund_id is None
        provider_refund_id = f"rfnd_{uuid4().hex}"

        handled = _process_refund_event(db, {
            "event": "refund.processed",
            "payload": {"refund": {"entity": {
                "id": provider_refund_id,
                "payment_id": refund.provider_payment_id,
                "amount": 12000, "currency": "INR", "status": "processed",
            }}},
        })
        assert handled is True
        db.commit()
        db.refresh(refund)
        db.refresh(order)
        assert refund.provider_refund_id == provider_refund_id
        assert refund.status == "succeeded"
        assert order.payment_status == PaymentStatus.REFUNDED


def test_refund_dispatch_reacquires_order_before_refund_after_provider_call(monkeypatch) -> None:
    """The post-provider transaction must not invert cancellation's lock order."""
    _enable_provider(monkeypatch)
    monkeypatch.setattr(
        refund_service, "create_razorpay_refund",
        _ProviderSpy(result={"id": _rid("rfnd_order_first"), "status": "processed"}),
    )
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        locked = []

        def observe(state):
            stmt = state.statement
            if getattr(stmt, "_for_update_arg", None) is None:
                return
            sql = str(stmt)
            if "FROM orders" in sql:
                locked.append("order")
            elif "FROM payment_refunds" in sql:
                locked.append("refund")

        event.listen(db, "do_orm_execute", observe)
        try:
            assert dispatch_refund(db, refund.id) == REFUND_SUCCEEDED
        finally:
            event.remove(db, "do_orm_execute", observe)
        # Initial refund claim commits before the provider call. The next
        # transaction must lock the order before reacquiring the refund.
        assert locked[:3] == ["refund", "order", "refund"]


@pytest.mark.parametrize("scenario", ["timeout", "server_error", "missing_refund_id"])
def test_refund_provider_uncertain_outcomes_are_not_retryable(monkeypatch, scenario) -> None:
    """An ambiguous refund response is not proof that Razorpay rejected it."""

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, *, auth, headers, json):
            request = httpx.Request("POST", url)
            if scenario == "timeout":
                raise httpx.ReadTimeout("timed out", request=request)
            if scenario == "server_error":
                return httpx.Response(503, request=request, json={"error": "unavailable"})
            return httpx.Response(200, request=request, json={"status": "processed"})

    monkeypatch.setattr(payment_service.httpx, "Client", Client)
    monkeypatch.setattr(payment_service.settings, "RAZORPAY_KEY_ID", "rzp_test_example")
    monkeypatch.setattr(payment_service.settings, "RAZORPAY_KEY_SECRET", "test-secret")
    with pytest.raises(payment_service.PaymentProviderIndeterminate):
        payment_service.create_razorpay_refund(
            provider_payment_id="pay_provider",
            amount=Decimal("55.00"),
            idempotency_key=f"order-refund:{uuid4()}",
        )


def test_indeterminate_refund_is_quarantined_without_automatic_retry(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    spy = _ProviderSpy(
        error=payment_service.PaymentProviderIndeterminate("Refund outcome unknown")
    )
    monkeypatch.setattr(refund_service, "create_razorpay_refund", spy)
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()

        assert dispatch_refund(db, refund.id) == REFUND_PROCESSING
        db.refresh(refund)
        db.refresh(order)
        assert refund.attempt_count == 1
        assert refund.status == REFUND_PROCESSING
        assert "manual reconciliation" in (refund.failure_reason or "")
        assert order.payment_status == PaymentStatus.REFUND_PENDING
        assert refund.id not in refund_service.due_refund_ids(db, order_id=order.id)
        assert dispatch_refund(db, refund.id) == REFUND_PROCESSING
        assert len(spy.calls) == 1


def test_concurrent_refund_webhook_success_survives_provider_error(monkeypatch) -> None:
    """A webhook may settle the refund while the original HTTP call times out."""
    _enable_provider(monkeypatch)
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        db.commit()
        refund_id = refund.id
        provider_refund_id = _rid("rfnd_concurrent_success")

        def provider_call(**_kwargs):
            # The dispatcher has committed its claim before network I/O.
            # Simulate the independently verified webhook winning that race.
            current = db.get(PaymentRefund, refund_id)
            refund_service.apply_provider_refund_result(
                db, current, {"id": provider_refund_id, "status": "processed"}
            )
            db.commit()
            raise payment_service.PaymentProviderIndeterminate("timeout after acceptance")

        monkeypatch.setattr(refund_service, "create_razorpay_refund", provider_call)
        assert dispatch_refund(db, refund_id) == REFUND_SUCCEEDED
        db.refresh(refund)
        db.refresh(order)
        assert refund.status == REFUND_SUCCEEDED
        assert refund.provider_refund_id == provider_refund_id
        assert order.payment_status == PaymentStatus.REFUNDED
