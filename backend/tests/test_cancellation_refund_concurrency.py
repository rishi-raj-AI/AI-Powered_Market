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
