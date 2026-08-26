import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.integrations import PaymentAttempt
from app.models.orders import Order, PaymentMethod, PaymentStatus
from app.models.user import User
from app.schemas.integrations import (
    PaymentConfigResponse,
    PaymentIntentResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
)
from app.services.payments import (
    PaymentProviderError,
    PaymentProviderUnavailable,
    amount_to_subunits,
    create_razorpay_order,
    razorpay_enabled,
    verify_razorpay_signature,
)

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.get("/config", response_model=PaymentConfigResponse)
def payment_config() -> PaymentConfigResponse:
    enabled = razorpay_enabled()
    return PaymentConfigResponse(
        enabled=enabled,
        provider="razorpay",
        key_id=settings.RAZORPAY_KEY_ID if enabled else None,
    )


@router.post("/orders/{order_id}/intent", response_model=PaymentIntentResponse)
def create_payment_intent(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentIntentResponse:
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.payment_method != PaymentMethod.UPI:
        raise HTTPException(status_code=409, detail="This order is not configured for online payment")
    if order.payment_status == PaymentStatus.PAID:
        raise HTTPException(status_code=409, detail="Order is already paid")

    existing = db.scalar(
        select(PaymentAttempt)
        .where(
            PaymentAttempt.order_id == order.id,
            PaymentAttempt.provider == "razorpay",
            PaymentAttempt.status.in_(["created", "attempted"]),
            PaymentAttempt.provider_order_id.is_not(None),
        )
        .order_by(PaymentAttempt.created_at.desc())
    )
    if existing and existing.provider_order_id:
        if not settings.RAZORPAY_KEY_ID:
            raise HTTPException(status_code=503, detail="Payment provider is not configured")
        return PaymentIntentResponse(
            payment_attempt_id=existing.id,
            provider="razorpay",
            provider_order_id=existing.provider_order_id,
            amount_subunits=amount_to_subunits(existing.amount),
            amount=existing.amount,
            currency=existing.currency,
            key_id=settings.RAZORPAY_KEY_ID,
        )

    try:
        provider_order = create_razorpay_order(
            amount=order.total,
            receipt=order.order_number,
            gaonone_order_id=str(order.id),
        )
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PaymentProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    attempt = PaymentAttempt(
        order_id=order.id,
        provider="razorpay",
        provider_order_id=str(provider_order["id"]),
        status="created",
        amount=order.total,
        currency="INR",
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return PaymentIntentResponse(
        payment_attempt_id=attempt.id,
        provider="razorpay",
        provider_order_id=attempt.provider_order_id or "",
        amount_subunits=amount_to_subunits(attempt.amount),
        amount=attempt.amount,
        currency=attempt.currency,
        key_id=settings.RAZORPAY_KEY_ID or "",
    )


@router.post("/verify", response_model=PaymentVerifyResponse)
def verify_payment(
    payload: PaymentVerifyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentVerifyResponse:
    attempt = db.get(PaymentAttempt, payload.payment_attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Payment attempt not found")
    order = db.get(Order, attempt.order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if not attempt.provider_order_id:
        raise HTTPException(status_code=409, detail="Payment attempt has no provider order")

    if attempt.status == "paid" and attempt.provider_payment_id == payload.razorpay_payment_id:
        return PaymentVerifyResponse(
            order_id=order.id,
            payment_status=order.payment_status.value,
            provider_payment_id=payload.razorpay_payment_id,
        )

    try:
        valid = verify_razorpay_signature(
            provider_order_id=attempt.provider_order_id,
            provider_payment_id=payload.razorpay_payment_id,
            received_signature=payload.razorpay_signature,
        )
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not valid:
        attempt.status = "failed"
        order.payment_status = PaymentStatus.FAILED
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment signature")

    duplicate = db.scalar(
        select(PaymentAttempt).where(
            PaymentAttempt.provider_payment_id == payload.razorpay_payment_id,
            PaymentAttempt.id != attempt.id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Payment ID has already been used")

    attempt.provider_payment_id = payload.razorpay_payment_id
    attempt.status = "paid"
    order.payment_status = PaymentStatus.PAID
    db.commit()

    return PaymentVerifyResponse(
        order_id=order.id,
        payment_status=order.payment_status.value,
        provider_payment_id=payload.razorpay_payment_id,
    )
