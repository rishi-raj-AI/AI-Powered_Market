"""Unpaid reconciliation must quarantine cross-attempt provider identity collisions.

Disposable database fixtures and mocked Razorpay history only; no live money movement.
"""
from uuid import uuid4

import pytest

from app.models.integrations import PaymentAttempt
from app.models.orders import PaymentStatus
from app.scripts import audit_upi_payments
from tests.factories import make_order, session


@pytest.mark.parametrize("second_status", ["failed", "authorized", "captured"])
@pytest.mark.parametrize("reverse_history", [False, True])
def test_unpaid_audit_quarantines_reused_payment_id_across_retry_orders(
    monkeypatch, second_status, reverse_history
):
    with session() as db:
        order = make_order(
            db, payment_status=PaymentStatus.PENDING, with_paid_attempt=False
        )
        provider_orders = [f"order_{uuid4().hex}", f"order_{uuid4().hex}"]
        for provider_order_id in provider_orders:
            db.add(PaymentAttempt(
                order_id=order.id,
                provider="razorpay",
                provider_order_id=provider_order_id,
                provider_payment_id=None,
                status="failed",
                amount=order.total,
                currency="INR",
            ))
        db.commit()
        number = order.order_number
        shared_id = f"pay_{uuid4().hex}"
        histories = {
            provider_orders[0]: [{
                "id": shared_id, "order_id": provider_orders[0],
                "status": "failed", "amount": 12000, "currency": "INR",
            }],
            provider_orders[1]: [{
                "id": shared_id, "order_id": provider_orders[1],
                "status": second_status, "amount": 12000, "currency": "INR",
            }],
        }
        if reverse_history:
            # Reverse the local attempt order, not the identity conflict.
            attempts = db.query(PaymentAttempt).filter(
                PaymentAttempt.order_id == order.id
            ).all()
            attempts[0].provider_order_id, attempts[1].provider_order_id = (
                attempts[1].provider_order_id, attempts[0].provider_order_id
            )
            db.flush()
        monkeypatch.setattr(audit_upi_payments, "SessionLocal", lambda: db)
        monkeypatch.setattr(
            audit_upi_payments, "list_razorpay_order_payments",
            lambda *, provider_order_id: histories[provider_order_id],
        )
        report = audit_upi_payments.audit_unpaid_upi()
        finding = next(f for f in report["findings"] if f["order_number"] == number)
        assert finding["result"] == (
            "unexpected_capture" if second_status == "captured"
            else "payment_history_mismatch"
            if second_status == "failed" else "payment_history_mismatch"
        )
        assert report["no_capture_found"] == 0
        assert report["requires_review"] >= 1
