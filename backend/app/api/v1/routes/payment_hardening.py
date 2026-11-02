import hashlib
import json
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ensure_capability, get_current_user, get_db, require_roles
from app.core.capabilities import Capability
from app.models.commerce import Merchant, Store
from app.models.integrations import PaymentAttempt, PaymentRefund, PaymentWebhookEvent, SettlementEntry
from app.models.orders import Order, OrderStatus, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.integrations import PaymentVerifyRequest, PaymentVerifyResponse
from app.services.payments import (
    PaymentProviderError,
    PaymentProviderUnavailable,
    amount_to_subunits,
    fetch_razorpay_payment,
    verify_razorpay_signature,
    verify_razorpay_webhook_signature,
)
from app.services.refunds import (
    REFUND_REASON_ORPHANED_CAPTURE,
    REFUND_REASON_RETURNED,
    apply_provider_refund_result,
    ensure_refund_request,
    get_refund_for_order,
)
from app.services.settlements import ensure_settlement_entry
from app.services.notifications import enqueue_notification

router = APIRouter(prefix="/payments", tags=["Payments"])


def _lock_payment_context(
    db: Session,
    *,
    attempt_id: UUID | None = None,
    provider_order_id: str | None = None,
    user_id: UUID | None = None,
) -> tuple[PaymentAttempt | None, Order | None, bool]:
    """Lock a payment's commercial order before its provider attempt.

    Intent creation already locks the order while it looks up or records an
    attempt. Verification and webhook processing must take the same order of
    locks, otherwise an intent retry and a provider result can deadlock by each
    holding one side. Resolve the identifiers as columns first so this lookup
    does not leave a stale ORM entity in the session identity map.
    """
    identity_stmt = select(PaymentAttempt.id, PaymentAttempt.order_id)
    if attempt_id is not None:
        identity_stmt = identity_stmt.where(PaymentAttempt.id == attempt_id)
    elif provider_order_id is not None:
        identity_stmt = identity_stmt.where(PaymentAttempt.provider_order_id == provider_order_id)
    else:
        raise ValueError("A payment attempt identifier is required")
    identity = db.execute(identity_stmt).one_or_none()
    if identity is None:
        return None, None, False

    order_stmt = select(Order).where(Order.id == identity.order_id)
    if user_id is not None:
        order_stmt = order_stmt.where(Order.user_id == user_id)
    order = db.scalar(order_stmt.with_for_update())
    if order is None:
        return None, None, True

    attempt = db.scalar(
        select(PaymentAttempt)
        .where(PaymentAttempt.id == identity.id, PaymentAttempt.order_id == order.id)
        .with_for_update()
    )
    return attempt, order, True



def _confirmed_capture(attempt: PaymentAttempt, provider_payment_id: str) -> bool:
    """Signature proves callback authenticity; only provider capture proves payment."""
    try:
        entity = fetch_razorpay_payment(provider_payment_id=provider_payment_id)
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail="Payment verification is unavailable") from exc
    except PaymentProviderError as exc:
        raise HTTPException(status_code=502, detail="Unable to verify payment with provider") from exc
    if (
        entity.get("id") != provider_payment_id
        or entity.get("order_id") != attempt.provider_order_id
        or entity.get("currency") != attempt.currency
        or entity.get("amount") != amount_to_subunits(attempt.amount)
    ):
        raise HTTPException(status_code=409, detail="Provider payment does not match this order")
    return entity.get("status") == "captured"



def _notify_payment_captured(db: Session, order: Order) -> None:
    """Only first verified capture releases a pending UPI order to its merchant."""
    data = {"order_id": str(order.id), "order_number": order.order_number}
    enqueue_notification(
        db, user_id=order.user_id, event_type="order.payment_confirmed",
        title="Payment confirmed",
        body=f"Payment for order {order.order_number} was confirmed.",
        data=data,
    )
    store = db.get(Store, order.store_id)
    merchant = db.get(Merchant, store.merchant_id) if store else None
    if merchant is not None:
        enqueue_notification(
            db, user_id=merchant.owner_user_id,
            event_type="merchant.order_received", title="New paid order",
            body=f"Paid order {order.order_number} is waiting for confirmation.",
            data=data,
        )


def _apply_paid(db: Session, attempt: PaymentAttempt, order: Order, provider_payment_id: str | None) -> None:
    if provider_payment_id:
        # A second capture is a separate financial obligation. Never silently
        # replace an already captured payment ID or settle it as the same sale.
        # Keep the webhook unprocessed for explicit financial reconciliation.
        if attempt.provider_payment_id and attempt.provider_payment_id != provider_payment_id:
            raise HTTPException(status_code=409, detail="Multiple captures require reconciliation")
        another_capture = db.scalar(
            select(PaymentAttempt.id).where(
                PaymentAttempt.order_id == order.id,
                PaymentAttempt.id != attempt.id,
                PaymentAttempt.status == "paid",
                PaymentAttempt.provider_payment_id.is_not(None),
            ).limit(1)
        )
        if another_capture is not None:
            raise HTTPException(status_code=409, detail="Multiple captures require reconciliation")
        duplicate = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.provider_payment_id == provider_payment_id,
                PaymentAttempt.id != attempt.id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Payment ID has already been used")
        attempt.provider_payment_id = provider_payment_id

    # A previously recorded refund obligation may lack the payment ID if a
    # cancellation raced provider capture. Attach the verified ID so the
    # refund dispatcher can actually return the customer's money.
    if order.payment_status == PaymentStatus.REFUND_PENDING:
        refund = get_refund_for_order(db, order.id)
        if refund is not None and refund.provider_payment_id is None and provider_payment_id:
            refund.provider_payment_id = provider_payment_id
            refund.payment_attempt_id = attempt.id

    # Provider capture is a financial fact, but it must not reopen a cancelled
    # commercial order or recreate merchant settlement after cancellation/refund.
    attempt.status = "paid"
    # SessionLocal uses autoflush=False. Persist the captured attempt within the
    # current transaction before refund lookup, otherwise the refund obligation
    # is created without its provider payment ID and cannot be dispatched.
    db.flush()
    if order.status in {OrderStatus.CANCELLED, OrderStatus.RETURNED} or order.payment_status in {
        PaymentStatus.REFUNDED,
        PaymentStatus.REFUND_PENDING,
    }:
        # Real money was captured for an order that will never be fulfilled.
        # Record the debt instead of absorbing it into an attempt/order status
        # mismatch that nothing would ever act on.
        if order.status in {OrderStatus.CANCELLED, OrderStatus.RETURNED} and order.payment_status not in {
            PaymentStatus.REFUNDED,
            PaymentStatus.REFUND_PENDING,
        }:
            order.payment_status = PaymentStatus.PAID
            ensure_refund_request(
                db, order,
                reason=(REFUND_REASON_RETURNED if order.status == OrderStatus.RETURNED
                        else REFUND_REASON_ORPHANED_CAPTURE),
            )
        return

    first_capture = order.payment_status != PaymentStatus.PAID
    order.payment_status = PaymentStatus.PAID
    if first_capture:
        ensure_settlement_entry(db, order)


def _apply_failed(attempt: PaymentAttempt, order: Order) -> None:
    # A late/invalid provider event must never overwrite terminal cancellation or
    # refund state. Active unpaid orders may still transition to payment failed.
    if order.status in {OrderStatus.CANCELLED, OrderStatus.RETURNED} or order.payment_status in {
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
    attempt, order, attempt_exists = _lock_payment_context(
        db,
        attempt_id=payload.payment_attempt_id,
        user_id=user.id,
    )
    if not attempt_exists:
        raise HTTPException(status_code=404, detail="Payment attempt not found")
    if attempt is None or order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if not attempt.provider_order_id:
        raise HTTPException(status_code=409, detail="Payment attempt has no provider order")
    try:
        valid = verify_razorpay_signature(
            provider_order_id=attempt.provider_order_id,
            provider_payment_id=payload.razorpay_payment_id,
            received_signature=payload.razorpay_signature,
        )
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not valid:
        # Never let an unauthenticated callback alter financial state.
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    if not _confirmed_capture(attempt, payload.razorpay_payment_id):
        # Authorized or still processing is not a captured payment. Do not
        # mark it failed: a later webhook may confirm a legitimate capture.
        raise HTTPException(status_code=409, detail="Payment is not captured yet")

    previously_paid = order.payment_status == PaymentStatus.PAID
    _apply_paid(db, attempt, order, payload.razorpay_payment_id)
    if not previously_paid and order.payment_status == PaymentStatus.PAID and order.status == OrderStatus.PLACED:
        _notify_payment_captured(db, order)
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
    # A signed provider event is not proof that it belongs to this refund.
    # Never apply a refund outcome for another payment, refund ID, or amount.
    # Amount is in paise in Razorpay's refund entity.
    if (
        not provider_refund_id
        or not refund_payment_id
        or not refund.provider_payment_id
        or refund_payment_id != refund.provider_payment_id
        or (refund.provider_refund_id is not None and provider_refund_id != refund.provider_refund_id)
        or refund_entity.get("currency") not in (None, refund.currency)
        or type(refund_entity.get("amount")) is not int
        or refund_entity["amount"] != amount_to_subunits(refund.amount)
    ):
        return False
    # Do not allow a late failed/pending event to reverse a completed refund.
    if refund.status == "succeeded" and refund_entity.get("status") != "processed":
        return True
    apply_provider_refund_result(db, refund, refund_entity)
    return True


def _process_event(db: Session, payload: dict) -> bool:
    event = str(payload.get("event") or "")
    if event.startswith("refund."):
        return _process_refund_event(db, payload)
    payment_entity = (((payload.get("payload") or {}).get("payment") or {}).get("entity") or {})
    order_entity = (((payload.get("payload") or {}).get("order") or {}).get("entity") or {})
    provider_payment_id = str(payment_entity.get("id") or "") or None
    provider_order_id = str(payment_entity.get("order_id") or order_entity.get("id") or "") or None
    if not provider_order_id:
        return event not in {"order.paid", "payment.captured"}
    attempt, order, _ = _lock_payment_context(db, provider_order_id=provider_order_id)
    if attempt is None or order is None:
        return False
    if event in {"order.paid", "payment.captured"}:
        if not provider_payment_id:
            return False
        try:
            captured = _confirmed_capture(attempt, provider_payment_id)
        except HTTPException as exc:
            if exc.status_code == 409:
                # Mismatched signed events must never change the order.
                return True
            raise
        if not captured:
            # Authorized/processing is not terminal; keep the event for replay.
            return False
        previously_paid = order.payment_status == PaymentStatus.PAID
        _apply_paid(db, attempt, order, provider_payment_id)
        if not previously_paid and order.payment_status == PaymentStatus.PAID and order.status == OrderStatus.PLACED:
            _notify_payment_captured(db, order)
    elif event == "payment.failed":
        _apply_failed(attempt, order)
    return True


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
        # A duplicate delivery cannot discard an earlier deferred capture.
        # The durable replay worker will retry rows without processed_at.
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

    if _process_event(db, payload):
        event.processed_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.get("/settlements")
def list_settlements(
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
):
    if user.role == UserRole.ADMIN:
        ensure_capability(user, Capability.SETTLEMENT_READ)
    stmt = select(SettlementEntry).order_by(SettlementEntry.created_at.desc())
    if user.role == UserRole.MERCHANT:
        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
        if merchant is None:
            return []
        stmt = stmt.where(SettlementEntry.merchant_id == merchant.id)
    entries = db.scalars(stmt.offset(offset).limit(limit)).all()
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
            "voided_at": entry.voided_at,
            "void_reason": entry.void_reason,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]
