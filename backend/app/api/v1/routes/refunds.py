import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_capability, get_current_user, get_db, require_capability
from app.core.capabilities import Capability
from app.models.integrations import PaymentRefund
from app.models.orders import Order
from app.models.user import User, UserRole
from app.schemas.integrations import PaymentRefundRead
from app.services.refunds import (
    OPEN_REFUND_STATUSES,
    dispatch_refund,
    get_refund_for_order,
)
from app.services.governance_audit import record_admin_action

router = APIRouter(tags=["Refunds"])


@router.get("/orders/{order_id}/refund", response_model=PaymentRefundRead)
def my_order_refund(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Let a customer see the real state of money owed back to them."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.role == UserRole.ADMIN:
        ensure_capability(user, Capability.REFUND_READ)
    if order.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="You cannot view this refund")
    refund = get_refund_for_order(db, order.id)
    if refund is None:
        raise HTTPException(status_code=404, detail="No refund has been requested for this order")
    return refund


@router.get("/admin/refunds", response_model=list[PaymentRefundRead])
def admin_refunds(
    open_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.REFUND_READ)),
):
    """Operational view of every refund, defaulting to money still owed."""
    stmt = select(PaymentRefund).order_by(PaymentRefund.requested_at.desc())
    if open_only:
        stmt = stmt.where(PaymentRefund.status.in_(tuple(OPEN_REFUND_STATUSES)))
    return db.scalars(stmt.offset(offset).limit(limit)).all()


@router.post("/admin/refunds/{refund_id}/retry", response_model=PaymentRefundRead)
def admin_retry_refund(
    refund_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.REFUND_WRITE)),
):
    """Manual recovery path for a refund the automatic worker could not settle."""
    refund = db.get(PaymentRefund, refund_id)
    if refund is None:
        raise HTTPException(status_code=404, detail="Refund not found")
    # An operator retry is a deliberate act, so it clears the automatic
    # attempt ceiling rather than silently doing nothing.
    previous = {"status": refund.status, "attempt_count": refund.attempt_count}
    if refund.attempt_count > 0 and refund.status == "failed":
        refund.attempt_count = 0
    record_admin_action(
        db,
        request=request,
        actor=admin,
        action="refund.retry_requested",
        capability=Capability.REFUND_WRITE,
        resource_type="payment_refund",
        resource_id=refund.id,
        previous_state=previous,
        resulting_state={"status": refund.status, "attempt_count": refund.attempt_count},
        reason="manual_refund_retry",
    )
    # Persist the attributed retry request before the provider operation. The
    # provider dispatcher has its own durable state transitions and commits.
    db.commit()
    dispatch_refund(db, refund_id)
    refreshed = db.get(PaymentRefund, refund_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Refund not found")
    return refreshed
