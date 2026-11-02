"""PostgreSQL acceptance for cancellation racing a provider-confirmed refund.

Only disposable test orders and signed-event-shaped mock payloads are used.
The test never invokes Razorpay or changes live financial records.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.v1.routes import orders
from app.api.v1.routes.payment_hardening import _process_refund_event
from app.models.commerce import StoreProduct
from app.models.integrations import PaymentRefund
from app.models.orders import Order, OrderItem, OrderStatus, PaymentStatus
from app.models.user import User
from app.services import refunds
from app.services.payments import amount_to_subunits
from app.services.refunds import REFUND_REASON_CANCELLED, ensure_refund_request
from tests.factories import make_order, session


@pytest.mark.parametrize("first_operation", ["cancel", "webhook"])
def test_cancel_and_processed_refund_webhook_serialize_without_deadlock(
    monkeypatch, first_operation,
):
    """Both lock orders must finish, with one stock restore and one settlement reversal."""
    with session() as db:
        order = make_order(db, payment_status=PaymentStatus.PAID)
        db.commit()
        refund = ensure_refund_request(db, order, reason=REFUND_REASON_CANCELLED)
        assert refund is not None and refund.provider_payment_id
        db.commit()
        order_id = order.id
        user_id = order.user_id
        refund_id = refund.id
        payment_id = refund.provider_payment_id
        amount = refund.amount
        item = db.scalar(select(OrderItem).where(OrderItem.order_id == order_id))
        listing_id = db.scalar(
            select(StoreProduct.id).where(
                StoreProduct.store_id == order.store_id,
                StoreProduct.product_id == item.product_id,
            )
        )
        initial_stock = db.get(StoreProduct, listing_id).stock_quantity

    payload = {
        "event": "refund.processed",
        "payload": {"refund": {"entity": {
            "id": f"rfnd_cancel_race_{uuid4().hex}",
            "payment_id": payment_id,
            "amount": amount_to_subunits(amount),
            "currency": "INR",
            "status": "processed",
        }}},
    }
    first_holding_order = Event()
    release_first = Event()
    second_started = Event()
    second_finished = Event()
    settlements = []
    settlement_lock = Lock()
    original_restore = orders._restore_cancelled_stock

    def restore_stock(db, locked_order):
        if first_operation == "cancel":
            first_holding_order.set()
            assert release_first.wait(timeout=15), "Cancellation lock hold timed out"
        return original_restore(db, locked_order)

    def settle_once(_db, locked_order):
        with settlement_lock:
            settlements.append(locked_order.id)
        if first_operation == "webhook":
            first_holding_order.set()
            assert release_first.wait(timeout=15), "Webhook lock hold timed out"

    monkeypatch.setattr(orders, "_restore_cancelled_stock", restore_stock)
    monkeypatch.setattr(refunds, "settle_refunded_order", settle_once)

    def cancel():
        with session() as db:
            user = db.get(User, user_id)
            return orders.cancel_my_order(order_id=order_id, db=db, user=user).status

    def webhook():
        with session() as db:
            result = _process_refund_event(db, payload)
            db.commit()
            return result

    def competing(operation):
        second_started.set()
        try:
            return operation()
        finally:
            second_finished.set()

    first = cancel if first_operation == "cancel" else webhook
    second = webhook if first_operation == "cancel" else cancel
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(first)
            assert first_holding_order.wait(timeout=15), "First operation did not lock order"
            second_future = executor.submit(competing, second)
            assert second_started.wait(timeout=15)
            assert not second_finished.wait(timeout=0.25), (
                "Competing operation bypassed the held commercial order lock"
            )
            release_first.set()
            first_result = first_future.result(timeout=15)
            second_result = second_future.result(timeout=15)
    finally:
        release_first.set()

    assert (first_result, second_result) == (
        (OrderStatus.CANCELLED, True) if first_operation == "cancel"
        else (True, OrderStatus.CANCELLED)
    )
    assert settlements == [order_id]
    with session() as db:
        stored_order = db.get(Order, order_id)
        stored_refund = db.get(PaymentRefund, refund_id)
        assert stored_order.status == OrderStatus.CANCELLED
        assert stored_order.payment_status == PaymentStatus.REFUNDED
        assert stored_refund.status == refunds.REFUND_SUCCEEDED
        assert stored_refund.provider_refund_id == payload["payload"]["refund"]["entity"]["id"]
        assert db.get(StoreProduct, listing_id).stock_quantity == initial_stock + 1


@pytest.mark.parametrize("first_operation", ["cancel", "capture"])
def test_cancel_and_verified_capture_preserve_refund_obligation(
    monkeypatch, first_operation,
):
    """A late capture is refunded, never used to reopen a cancelled order."""
    from decimal import Decimal

    from app.api.v1.routes import payment_hardening
    from app.models.integrations import PaymentAttempt

    with session() as db:
        order = make_order(
            db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False,
        )
        provider_order_id = f"order_cancel_race_{uuid4().hex}"
        provider_payment_id = f"pay_cancel_race_{uuid4().hex}"
        db.add(PaymentAttempt(
            order_id=order.id,
            provider="razorpay",
            provider_order_id=provider_order_id,
            status="attempted",
            amount=Decimal("120.00"),
            currency="INR",
        ))
        db.commit()
        order_id, user_id = order.id, order.user_id

    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": provider_payment_id, "order_id": provider_order_id,
        }}},
    }
    first_holding_order = Event()
    release_first = Event()
    second_started = Event()
    second_finished = Event()
    settlements = []
    notifications = []
    original_restore = orders._restore_cancelled_stock

    def restore_stock(db, locked_order):
        if first_operation == "cancel":
            first_holding_order.set()
            assert release_first.wait(timeout=15), "Cancellation lock hold timed out"
        return original_restore(db, locked_order)

    def provider_capture(*, provider_payment_id: str):
        if first_operation == "capture":
            first_holding_order.set()
            assert release_first.wait(timeout=15), "Capture lock hold timed out"
        return {
            "id": provider_payment_id,
            "order_id": provider_order_id,
            "amount": 12000,
            "currency": "INR",
            "status": "captured",
        }

    monkeypatch.setattr(orders, "_restore_cancelled_stock", restore_stock)
    monkeypatch.setattr(payment_hardening, "fetch_razorpay_payment", provider_capture)
    monkeypatch.setattr(
        payment_hardening, "ensure_settlement_entry",
        lambda _db, order: settlements.append(order.id),
    )
    monkeypatch.setattr(
        payment_hardening, "_notify_payment_captured",
        lambda _db, order: notifications.append(order.id),
    )

    def cancel():
        with session() as db:
            user = db.get(User, user_id)
            return orders.cancel_my_order(order_id=order_id, db=db, user=user).status

    def capture():
        with session() as db:
            result = payment_hardening._process_event(db, payload)
            db.commit()
            return result

    first = cancel if first_operation == "cancel" else capture
    second = capture if first_operation == "cancel" else cancel

    def competing():
        second_started.set()
        try:
            return second()
        finally:
            second_finished.set()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(first)
            assert first_holding_order.wait(timeout=15), "First operation did not lock order"
            second_future = executor.submit(competing)
            assert second_started.wait(timeout=15)
            assert not second_finished.wait(timeout=0.25), (
                "Competing operation bypassed the held commercial order lock"
            )
            release_first.set()
            first_result = first_future.result(timeout=15)
            second_result = second_future.result(timeout=15)
    finally:
        release_first.set()

    assert (first_result, second_result) == (
        (OrderStatus.CANCELLED, True) if first_operation == "cancel"
        else (True, OrderStatus.CANCELLED)
    )
    with session() as db:
        stored_order = db.get(Order, order_id)
        refund = db.scalar(select(PaymentRefund).where(PaymentRefund.order_id == order_id))
        attempt = db.scalar(select(PaymentAttempt).where(PaymentAttempt.order_id == order_id))
        assert stored_order.status == OrderStatus.CANCELLED
        assert stored_order.payment_status == PaymentStatus.REFUND_PENDING
        assert attempt.status == "paid"
        assert attempt.provider_payment_id == provider_payment_id
        assert refund is not None
        assert refund.provider_payment_id == provider_payment_id
        assert refund.status == refunds.REFUND_REQUESTED
    # Capture before cancellation can create a settlement, but cancellation
    # after capture must create the matching refund debt. Late capture never
    # releases fulfilment or sends a new merchant order notification.
    expected = [] if first_operation == "cancel" else [order_id]
    assert settlements == expected
    assert notifications == expected
