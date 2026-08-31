import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.integrations import PaymentRefund
from app.models.orders import Order
from app.models.user import User, UserRole
from app.schemas.integrations import PaymentRefundRead
from app.services.refunds import (
    OPEN_REFUND_STATUSES,
    dispatch_refund,
    get_refund_for_order,
)

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
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Operational view of every refund, defaulting to money still owed."""
    stmt = select(PaymentRefund).order_by(PaymentRefund.requested_at.desc())
    if open_only:
        stmt = stmt.where(PaymentRefund.status.in_(tuple(OPEN_REFUND_STATUSES)))
    return db.scalars(stmt.offset(offset).limit(limit)).all()


@router.post("/admin/refunds/{refund_id}/retry", response_model=PaymentRefundRead)
def admin_retry_refund(
    refund_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Manual recovery path for a refund the automatic worker could not settle."""
    refund = db.get(PaymentRefund, refund_id)
    if refund is None:
        raise HTTPException(status_code=404, detail="Refund not found")
    # An operator retry is a deliberate act, so it clears the automatic
    # attempt ceiling rather than silently doing nothing.
    if refund.attempt_count > 0 and refund.status == "failed":
        refund.attempt_count = 0
        db.commit()
    dispatch_refund(db, refund_id)
    refreshed = db.get(PaymentRefund, refund_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Refund not found")
    return refreshed
