import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.commerce import Merchant, Store
from app.models.integrations import CodCollection
from app.models.orders import (
    Delivery,
    DeliveryProof,
    DeliveryStatus,
    Order,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    StatusTransitionEvent,
)
from app.models.user import User, UserRole
from app.schemas.cod import CodCollectionRead, CodCollectionRequest
from app.schemas.orders import (
    DeliveryFailureRequest,
    DeliveryProofChallengeRead,
    DeliveryProofRead,
    DeliveryProofSubmit,
    DeliveryRead,
    StatusTransitionEventRead,
)
from app.services.notifications import enqueue_notification
from app.services.order_transitions import (
    can_transition_delivery,
    can_transition_order,
    transition_delivery,
    transition_order,
)

router = APIRouter(tags=["Delivery Operations"])
OTP_TTL_MINUTES = 15


def _otp_hash(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def _locked_delivery_order(db: Session, delivery_id: uuid.UUID) -> tuple[Delivery, Order]:
    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    order = db.scalar(select(Order).where(Order.id == delivery.order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=409, detail="Delivery order is missing")
    return delivery, order


def _require_assigned_rider(delivery: Delivery, user: User) -> None:
    if user.role != UserRole.ADMIN and delivery.delivery_partner_id != user.id:
        raise HTTPException(status_code=403, detail="Delivery is not assigned to you")


def _can_view_order(db: Session, order: Order, user: User) -> bool:
    if user.role == UserRole.ADMIN or order.user_id == user.id:
        return True
    if user.role == UserRole.MERCHANT:
        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
        store = db.get(Store, order.store_id)
        return bool(merchant and store and store.merchant_id == merchant.id)
    if user.role == UserRole.DELIVERY:
        delivery = db.scalar(select(Delivery).where(Delivery.order_id == order.id))
        return bool(delivery and delivery.delivery_partner_id == user.id)
    return False


@router.post("/delivery/{delivery_id}/fail", response_model=DeliveryRead)
def fail_delivery(
    delivery_id: uuid.UUID,
    payload: DeliveryFailureRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    delivery, order = _locked_delivery_order(db, delivery_id)
    _require_assigned_rider(delivery, user)
    if delivery.status not in {DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP}:
        raise HTTPException(status_code=409, detail="Only an active delivery can be failed")

    transition_delivery(delivery, DeliveryStatus.FAILED)
    delivery.failed_at = datetime.now(timezone.utc)
    delivery.failure_reason = payload.reason
    delivery.failure_notes = payload.notes
    delivery.failure_evidence_url = payload.evidence_url

    enqueue_notification(
        db,
        user_id=order.user_id,
        event_type="delivery.failed",
        title="Delivery needs attention",
        body=f"Delivery for order {order.order_number} could not be completed. Our operations team will review it.",
        data={"order_id": str(order.id), "delivery_id": str(delivery.id), "reason": payload.reason},
    )
    db.commit()
    db.refresh(delivery)
    return delivery


@router.post("/admin/deliveries/{delivery_id}/recover", response_model=DeliveryRead)
def recover_failed_delivery(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    delivery, order = _locked_delivery_order(db, delivery_id)
    if delivery.status != DeliveryStatus.FAILED:
        raise HTTPException(status_code=409, detail="Only a failed delivery can be recovered")
    if order.status != OrderStatus.READY or delivery.picked_up_at is not None:
        raise HTTPException(
            status_code=409,
            detail="A delivery can only be reassigned after failure if custody never left the merchant",
        )

    delivery.delivery_partner_id = None
    transition_delivery(delivery, DeliveryStatus.UNASSIGNED)
    delivery.assigned_at = None
    enqueue_notification(
        db,
        user_id=order.user_id,
        event_type="delivery.reassignment",
        title="Delivery partner is being reassigned",
        body=f"We are assigning another delivery partner to order {order.order_number}.",
        data={"order_id": str(order.id), "delivery_id": str(delivery.id)},
    )
    db.commit()
    db.refresh(delivery)
    return delivery


@router.post("/delivery/{delivery_id}/proof/challenge", response_model=DeliveryProofChallengeRead)
def issue_delivery_proof_challenge(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    delivery, order = _locked_delivery_order(db, delivery_id)
    _require_assigned_rider(delivery, user)
    if delivery.status != DeliveryStatus.PICKED_UP or order.status != OrderStatus.OUT_FOR_DELIVERY:
        raise HTTPException(status_code=409, detail="Proof challenge is available only after pickup")

    otp = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
    proof = db.scalar(select(DeliveryProof).where(DeliveryProof.delivery_id == delivery.id).with_for_update())
    if proof is None:
        proof = DeliveryProof(delivery_id=delivery.id, otp_hash=_otp_hash(otp), otp_expires_at=expires_at)
        db.add(proof)
    else:
        proof.otp_hash = _otp_hash(otp)
        proof.otp_expires_at = expires_at
        proof.verified_at = None

    enqueue_notification(
        db,
        user_id=order.user_id,
        event_type="delivery.otp",
        title="Delivery verification code",
        body=f"Your GaonOne delivery code is {otp}. Share it only after receiving order {order.order_number}.",
        data={"order_id": str(order.id), "delivery_id": str(delivery.id), "expires_at": expires_at.isoformat()},
    )
    db.commit()
    return DeliveryProofChallengeRead(delivery_id=delivery.id, expires_at=expires_at)


@router.post("/delivery/{delivery_id}/proof", response_model=DeliveryProofRead)
def verify_delivery_proof(
    delivery_id: uuid.UUID,
    payload: DeliveryProofSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    delivery, order = _locked_delivery_order(db, delivery_id)
    _require_assigned_rider(delivery, user)
    if delivery.status != DeliveryStatus.PICKED_UP or order.status != OrderStatus.OUT_FOR_DELIVERY:
        raise HTTPException(status_code=409, detail="Delivery proof can only be verified after pickup")

    proof = db.scalar(select(DeliveryProof).where(DeliveryProof.delivery_id == delivery.id).with_for_update())
    if proof is None:
        raise HTTPException(status_code=409, detail="Generate a delivery verification challenge first")
    now = datetime.now(timezone.utc)
    if proof.otp_expires_at < now:
        raise HTTPException(status_code=409, detail="Delivery verification code expired")
    if not hmac.compare_digest(proof.otp_hash, _otp_hash(payload.otp)):
        raise HTTPException(status_code=422, detail="Invalid delivery verification code")

    proof.verified_at = now
    proof.evidence_url = payload.evidence_url
    proof.recipient_name = payload.recipient_name
    proof.notes = payload.notes
    db.commit()
    db.refresh(proof)
    return proof


@router.get("/delivery/{delivery_id}/proof", response_model=DeliveryProofRead)
def get_delivery_proof(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    delivery = db.get(Delivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    order = db.get(Order, delivery.order_id)
    if order is None or not _can_view_order(db, order, user):
        raise HTTPException(status_code=403, detail="You cannot view this delivery proof")
    proof = db.scalar(select(DeliveryProof).where(DeliveryProof.delivery_id == delivery.id))
    if proof is None:
        raise HTTPException(status_code=404, detail="Delivery proof not found")
    return proof


@router.post("/delivery/{delivery_id}/cod-collection", response_model=CodCollectionRead)
def record_cod_collection(
    delivery_id: uuid.UUID,
    payload: CodCollectionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    delivery, order = _locked_delivery_order(db, delivery_id)
    _require_assigned_rider(delivery, user)
    if order.payment_method != PaymentMethod.COD:
        raise HTTPException(status_code=409, detail="Cash collection is only valid for COD orders")
    if delivery.status != DeliveryStatus.PICKED_UP or order.status != OrderStatus.OUT_FOR_DELIVERY:
        raise HTTPException(status_code=409, detail="COD collection can only be recorded after pickup")
    if payload.amount != order.total:
        raise HTTPException(status_code=422, detail="Collected COD amount must match the order total")

    existing = db.scalar(
        select(CodCollection).where(CodCollection.delivery_id == delivery.id).with_for_update()
    )
    if existing is not None:
        if existing.amount != order.total or existing.order_id != order.id:
            raise HTTPException(status_code=409, detail="A different COD collection is already recorded")
        return existing

    collection = CodCollection(
        delivery_id=delivery.id,
        order_id=order.id,
        amount=order.total,
        collected_by_user_id=user.id,
        collected_at=datetime.now(timezone.utc),
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


@router.post("/delivery/{delivery_id}/complete", response_model=DeliveryRead)
def complete_delivery(
    delivery_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.DELIVERY, UserRole.ADMIN)),
):
    delivery, order = _locked_delivery_order(db, delivery_id)
    _require_assigned_rider(delivery, user)
    if not can_transition_delivery(delivery.status, DeliveryStatus.DELIVERED):
        raise HTTPException(status_code=409, detail=f"Delivery cannot be completed from {delivery.status.value}")
    if not can_transition_order(order.status, OrderStatus.DELIVERED):
        raise HTTPException(status_code=409, detail=f"Order cannot be delivered from {order.status.value}")
    proof = db.scalar(select(DeliveryProof).where(DeliveryProof.delivery_id == delivery.id).with_for_update())
    if proof is None or proof.verified_at is None:
        raise HTTPException(status_code=409, detail="Verified proof of delivery is required")

    if order.payment_method == PaymentMethod.COD:
        collection = db.scalar(
            select(CodCollection).where(CodCollection.delivery_id == delivery.id).with_for_update()
        )
        if collection is None:
            raise HTTPException(status_code=409, detail="Recorded COD collection is required before completion")
        if collection.order_id != order.id or collection.amount != order.total:
            raise HTTPException(status_code=409, detail="Recorded COD collection does not match this order")

    transition_delivery(delivery, DeliveryStatus.DELIVERED)
    delivery.delivered_at = datetime.now(timezone.utc)
    transition_order(order, OrderStatus.DELIVERED)
    if order.payment_method == PaymentMethod.COD:
        order.payment_status = PaymentStatus.PAID

    enqueue_notification(
        db,
        user_id=order.user_id,
        event_type="order.delivered",
        title="Order delivered",
        body=f"Order {order.order_number} has been delivered. Thank you for using GaonOne.",
        data={"order_id": str(order.id), "delivery_id": str(delivery.id)},
    )
    db.commit()
    db.refresh(delivery)
    return delivery


@router.get("/orders/{order_id}/events", response_model=list[StatusTransitionEventRead])
def order_transition_events(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if not _can_view_order(db, order, user):
        raise HTTPException(status_code=403, detail="You cannot view this order history")
    return db.scalars(
        select(StatusTransitionEvent)
        .where(StatusTransitionEvent.order_id == order.id)
        .order_by(StatusTransitionEvent.created_at.asc(), StatusTransitionEvent.id.asc())
    ).all()
