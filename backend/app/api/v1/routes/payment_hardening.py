import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Merchant
from app.models.integrations import PaymentAttempt, PaymentRefund, PaymentWebhookEvent, SettlementEntry
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.integrations import PaymentVerifyRequest, PaymentVerifyResponse
from app.services.payments import PaymentProviderUnavailable, verify_razorpay_signature, verify_razorpay_webhook_signature
from app.services.refunds import (
    REFUND_REASON_ORPHANED_CAPTURE,
    apply_provider_refund_result,
    ensure_refund_request,
)
from app.services.settlements import ensure_settlement_entry

router = APIRouter(prefix="/payments", tags=["Payments"])


def _apply_paid(db: Session, attempt: PaymentAttempt, order: Order, provider_payment_id: str | None) -> None:
    if provider_payment_id:
        duplicate = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.provider_payment_id == provider_payment_id,
                PaymentAttempt.id != attempt.id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Payment ID has already been used")
        attempt.provider_payment_id = provider_payment_id

    # Provider capture is a financial fact, but it must not reopen a cancelled
    # commercial order or recreate merchant settlement after cancellation/refund.
    attempt.status = "paid"
    if order.status == OrderStatus.CANCELLED or order.payment_status in {
        PaymentStatus.REFUNDED,
        PaymentStatus.REFUND_PENDING,
    }:
        # Real money was captured for an order that will never be fulfilled.
        # Record the debt instead of absorbing it into an attempt/order status
        # mismatch that nothing would ever act on.
        if order.status == OrderStatus.CANCELLED and order.payment_status not in {
            PaymentStatus.REFUNDED,
            PaymentStatus.REFUND_PENDING,
        }:
            order.payment_status = PaymentStatus.PAID
            ensure_refund_request(db, order, reason=REFUND_REASON_ORPHANED_CAPTURE)
        return

    order.payment_status = PaymentStatus.PAID
    ensure_settlement_entry(db, order)


def _apply_failed(attempt: PaymentAttempt, order: Order) -> None:
    # A late/invalid provider event must never overwrite terminal cancellation or
    # refund state. Active unpaid orders may still transition to payment failed.
    if order.status == OrderStatus.CANCELLED or order.payment_status in {
        PaymentStatus.PAID,
        PaymentStatus.REFUNDED,
        PaymentStatus.REFUND_PENDING,
    }:
        return
    attempt.status = "failed"
    order.payment_status = PaymentStatus.FAILED


@router.post("/verify", response_model=PaymentVerifyResponse)
def hardened_verify_payment(
    payload: PaymentVerifyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentVerifyResponse:
    attempt = db.scalar(select(PaymentAttempt).where(PaymentAttempt.id == payload.payment_attempt_id).with_for_update())
    if attempt is None:
        raise HTTPException(status_code=404, detail="Payment attempt not found")
    order = db.scalar(select(Order).where(Order.id == attempt.order_id).with_for_update())
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if not attempt.provider_order_id:
        raise HTTPException(status_code=409, detail="Payment attempt has no provider order")
    if attempt.status == "paid" and attempt.provider_payment_id == payload.razorpay_payment_id:
        if order.status != OrderStatus.CANCELLED and order.payment_status not in {
            PaymentStatus.REFUNDED,
            PaymentStatus.REFUND_PENDING,
        }:
            ensure_settlement_entry(db, order)
        db.commit()
        return PaymentVerifyResponse(order_id=order.id, payment_status=order.payment_status.value, provider_payment_id=payload.razorpay_payment_id)

    try:
        valid = verify_razorpay_signature(
            provider_order_id=attempt.provider_order_id,
            provider_payment_id=payload.razorpay_payment_id,
            received_signature=payload.razorpay_signature,
        )
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not valid:
        _apply_failed(attempt, order)
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    _apply_paid(db, attempt, order, payload.razorpay_payment_id)
    db.commit()
    return PaymentVerifyResponse(order_id=order.id, payment_status=order.payment_status.value, provider_payment_id=payload.razorpay_payment_id)


def _process_refund_event(db: Session, payload: dict) -> bool:
    """Reconcile an asynchronous refund outcome reported by the provider."""
    refund_entity = (((payload.get("payload") or {}).get("refund") or {}).get("entity") or {})
    provider_refund_id = str(refund_entity.get("id") or "") or None
    refund_payment_id = str(refund_entity.get("payment_id") or "") or None
    if not provider_refund_id and not refund_payment_id:
        return False

    refund = None
    if provider_refund_id:
        refund = db.scalar(
            select(PaymentRefund).where(PaymentRefund.provider_refund_id == provider_refund_id).with_for_update()
        )
    if refund is None and refund_payment_id:
        refund = db.scalar(
            select(PaymentRefund)
            .where(PaymentRefund.provider_payment_id == refund_payment_id)
            .order_by(PaymentRefund.requested_at.desc())
            .with_for_update()
        )
    if refund is None:
        return False
    apply_provider_refund_result(db, refund, refund_entity)
    return True


def _process_event(db: Session, payload: dict) -> None:
    event = str(payload.get("event") or "")
    if event.startswith("refund."):
        _process_refund_event(db, payload)
        return
    payment_entity = (((payload.get("payload") or {}).get("payment") or {}).get("entity") or {})
    order_entity = (((payload.get("payload") or {}).get("order") or {}).get("entity") or {})
    provider_payment_id = str(payment_entity.get("id") or "") or None
    provider_order_id = str(payment_entity.get("order_id") or order_entity.get("id") or "") or None
    if not provider_order_id:
        return
    attempt = db.scalar(select(PaymentAttempt).where(PaymentAttempt.provider_order_id == provider_order_id).with_for_update())
    if attempt is None:
        return
    order = db.scalar(select(Order).where(Order.id == attempt.order_id).with_for_update())
    if order is None:
        return
    if event in {"order.paid", "payment.captured"}:
        _apply_paid(db, attempt, order, provider_payment_id)
    elif event == "payment.failed":
        _apply_failed(attempt, order)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def hardened_razorpay_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay signature")
    try:
        valid = verify_razorpay_webhook_signature(raw_body=raw_body, received_signature=signature)
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook payload")

    event_key = request.headers.get("x-razorpay-event-id") or hashlib.sha256(raw_body).hexdigest()
    existing = db.scalar(
        select(PaymentWebhookEvent).where(
            PaymentWebhookEvent.provider == "razorpay",
            PaymentWebhookEvent.event_key == event_key,
        )
    )
    if existing is not None:
        return {"ok": True}

    event = PaymentWebhookEvent(
        provider="razorpay",
        event_key=event_key,
        event_type=str(payload.get("event") or "unknown"),
        payload=payload,
    )
    db.add(event)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"ok": True}

    _process_event(db, payload)
    event.processed_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.get("/settlements")
def list_settlements(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    stmt = select(SettlementEntry).order_by(SettlementEntry.created_at.desc())
    if user.role == UserRole.MERCHANT:
        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
        if merchant is None:
            return []
        stmt = stmt.where(SettlementEntry.merchant_id == merchant.id)
    entries = db.scalars(stmt.limit(500)).all()
    return [
        {
            "id": str(entry.id),
            "order_id": str(entry.order_id),
            "store_id": str(entry.store_id),
            "merchant_id": str(entry.merchant_id),
            "payment_method": entry.payment_method,
            "gross_amount": str(entry.gross_amount),
            "merchant_amount": str(entry.merchant_amount),
            "delivery_fee_amount": str(entry.delivery_fee_amount),
            "status": entry.status,
            "settled_at": entry.settled_at,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]
