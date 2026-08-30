from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from app.api.v1.routes import payment_hardening
from app.models.integrations import PaymentAttempt
from app.models.orders import Order, OrderStatus, PaymentMethod, PaymentStatus


def _order(*, status: OrderStatus, payment_status: PaymentStatus) -> Order:
    return Order(
        id=uuid4(),
        order_number=f"GO-C04-{uuid4().hex[:8]}",
        user_id=uuid4(),
        store_id=uuid4(),
        address_id=uuid4(),
        status=status,
        payment_method=PaymentMethod.UPI,
        payment_status=payment_status,
        subtotal=Decimal("100.00"),
        delivery_fee=Decimal("20.00"),
        total=Decimal("120.00"),
    )


def _attempt(order: Order) -> PaymentAttempt:
    return PaymentAttempt(
        id=uuid4(),
        order_id=order.id,
        provider="razorpay",
        provider_order_id=f"order_{uuid4().hex}",
        status="attempted",
        amount=order.total,
        currency="INR",
    )


def test_paid_capture_updates_active_order_and_creates_settlement(monkeypatch) -> None:
    order = _order(status=OrderStatus.PLACED, payment_status=PaymentStatus.PENDING)
    attempt = _attempt(order)
    db = MagicMock()
    db.scalar.return_value = None
    ensure_settlement = MagicMock()
    monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", ensure_settlement)

    payment_hardening._apply_paid(db, attempt, order, "pay_active")

    assert attempt.status == "paid"
    assert attempt.provider_payment_id == "pay_active"
    assert order.payment_status == PaymentStatus.PAID
    ensure_settlement.assert_called_once_with(db, order)


def test_late_capture_does_not_reopen_cancelled_refunded_order(monkeypatch) -> None:
    order = _order(status=OrderStatus.CANCELLED, payment_status=PaymentStatus.REFUNDED)
    attempt = _attempt(order)
    db = MagicMock()
    db.scalar.return_value = None
    ensure_settlement = MagicMock()
    monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", ensure_settlement)

    payment_hardening._apply_paid(db, attempt, order, "pay_late")

    assert attempt.status == "paid"
    assert attempt.provider_payment_id == "pay_late"
    assert order.status == OrderStatus.CANCELLED
    assert order.payment_status == PaymentStatus.REFUNDED
    ensure_settlement.assert_not_called()


def test_late_capture_on_cancelled_order_owes_a_refund_and_never_settles(monkeypatch) -> None:
    """A capture that lands after cancellation is real money we now owe back.

    The order must not become commercially fulfillable (no settlement, still
    cancelled), but the capture must not vanish into an attempt/order status
    mismatch either: it leaves the order owing a refund.
    """
    order = _order(status=OrderStatus.CANCELLED, payment_status=PaymentStatus.PENDING)
    attempt = _attempt(order)
    db = MagicMock()
    db.scalar.return_value = None
    ensure_settlement = MagicMock()
    monkeypatch.setattr(payment_hardening, "ensure_settlement_entry", ensure_settlement)

    payment_hardening._apply_paid(db, attempt, order, "pay_late_pending")

    assert attempt.status == "paid"
    # Not commercially paid, and never settled to the merchant.
    assert order.payment_status is not PaymentStatus.PAID
    ensure_settlement.assert_not_called()
    # The captured money is recorded as owed back rather than silently absorbed.
    assert order.payment_status == PaymentStatus.REFUND_PENDING


def test_payment_failure_does_not_overwrite_refund_or_cancelled_state() -> None:
    refunded = _order(status=OrderStatus.CANCELLED, payment_status=PaymentStatus.REFUNDED)
    refunded_attempt = _attempt(refunded)
    payment_hardening._apply_failed(refunded_attempt, refunded)
    assert refunded_attempt.status == "attempted"
    assert refunded.payment_status == PaymentStatus.REFUNDED

    cancelled_pending = _order(status=OrderStatus.CANCELLED, payment_status=PaymentStatus.PENDING)
    pending_attempt = _attempt(cancelled_pending)
    payment_hardening._apply_failed(pending_attempt, cancelled_pending)
    assert pending_attempt.status == "attempted"
    assert cancelled_pending.payment_status == PaymentStatus.PENDING
