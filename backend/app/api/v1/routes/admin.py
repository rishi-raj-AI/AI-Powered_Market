import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_capability, get_db, require_capability
from app.core.capabilities import Capability, has_capability
from app.models.commerce import Merchant, MerchantStatus, Store, StoreProduct
from app.models.geography import Address, Village
from app.models.governance import AdministrativeAuditEvent
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus, PaymentStatus
from app.models.user import User, UserRole
from app.services.notifications import enqueue_notification
from app.services.order_transitions import transition_delivery
from app.services.delivery_performance import summarize_delivery_performance
from app.services.governance_audit import record_admin_action

router = APIRouter(prefix="/admin", tags=["Admin"])
ACTIVE_DELIVERY_STATUSES = {DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP}


class UserRoleUpdate(BaseModel):
    role: UserRole
    is_active: bool = True


class DeliveryAssignRequest(BaseModel):
    rider_id: uuid.UUID


def _audit_payload(event: AdministrativeAuditEvent) -> dict:
    return {
        "id": str(event.id),
        "actor_user_id": str(event.actor_user_id),
        "action": event.action,
        "capability": event.capability,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "previous_state": event.previous_state,
        "resulting_state": event.resulting_state,
        "reason": event.reason,
        "request_id": event.request_id,
        "created_at": event.created_at,
    }


def _user_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "phone": user.phone,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_super_admin": user.is_super_admin,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "created_at": user.created_at,
    }


def _delivery_payload(db: Session, delivery: Delivery) -> dict:
    order = db.get(Order, delivery.order_id)
    store = db.get(Store, order.store_id) if order else None
    address = db.get(Address, order.address_id) if order else None
    rider = db.get(User, delivery.delivery_partner_id) if delivery.delivery_partner_id else None
    return {
        "id": str(delivery.id),
        "order_id": str(delivery.order_id),
        "order_number": order.order_number if order else None,
        "delivery_partner_id": str(delivery.delivery_partner_id) if delivery.delivery_partner_id else None,
        "rider_name": rider.full_name if rider else None,
        "rider_phone": rider.phone if rider else None,
        "status": delivery.status.value,
        "assigned_at": delivery.assigned_at,
        "picked_up_at": delivery.picked_up_at,
        "failed_at": delivery.failed_at,
        "failure_reason": delivery.failure_reason,
        "failure_notes": delivery.failure_notes,
        "store_name": store.name if store else None,
        "store_landmark": store.landmark if store else None,
        "customer_landmark": address.landmark if address else None,
    }


@router.get("/users")
def admin_users(
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.USER_READ)),
):
    users = db.scalars(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return [_user_payload(user) for user in users]


@router.get("/audit-events")
def admin_audit_events(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.AUDIT_READ)),
):
    events = db.scalars(
        select(AdministrativeAuditEvent)
        .order_by(AdministrativeAuditEvent.created_at.desc(), AdministrativeAuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [_audit_payload(event) for event in events]


@router.patch("/users/{user_id}/role")
def admin_update_user(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.ADMIN_MANAGE)),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_super_admin:
        ensure_capability(admin, Capability.ADMIN_MANAGE)
        if user.id != admin.id or payload.role != UserRole.ADMIN or not payload.is_active:
            raise HTTPException(status_code=403, detail="Super Admin account is protected")
        return _user_payload(user)
    if payload.role != user.role or user.role == UserRole.ADMIN:
        ensure_capability(admin, Capability.ADMIN_MANAGE)
    if user.id == admin.id and (payload.role != UserRole.ADMIN or not payload.is_active):
        raise HTTPException(status_code=400, detail="You cannot remove or deactivate your own admin access")
    previous = {"role": user.role.value, "is_active": user.is_active, "is_verified": user.is_verified}
    user.role = payload.role
    user.is_active = payload.is_active
    record_admin_action(
        db,
        request=request,
        actor=admin,
        action="user.access_updated",
        capability=Capability.ADMIN_MANAGE,
        resource_type="user",
        resource_id=user.id,
        previous_state=previous,
        resulting_state={"role": user.role.value, "is_active": user.is_active, "is_verified": user.is_verified},
        reason="administrator_access_management",
    )
    db.commit()
    db.refresh(user)
    return _user_payload(user)


@router.get("/deliveries/active")
def admin_active_deliveries(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.RIDER_READ)),
):
    deliveries = db.scalars(
        select(Delivery)
        .where(Delivery.status.in_(ACTIVE_DELIVERY_STATUSES))
        .order_by(Delivery.updated_at.desc())
        .limit(limit)
    ).all()
    return [_delivery_payload(db, delivery) for delivery in deliveries]


@router.get("/deliveries/failed")
def admin_failed_deliveries(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.RIDER_READ)),
):
    """Return the operations queue for failed deliveries without changing state."""
    deliveries = db.scalars(
        select(Delivery)
        .join(Order, Order.id == Delivery.order_id)
        .where(
            Delivery.status == DeliveryStatus.FAILED,
            Order.status != OrderStatus.RETURNED,
        )
        .order_by(Delivery.failed_at.desc(), Delivery.updated_at.desc())
        .limit(limit)
    ).all()
    return [_delivery_payload(db, delivery) for delivery in deliveries]


@router.post("/deliveries/{delivery_id}/assign")
def admin_assign_delivery(
    delivery_id: uuid.UUID,
    payload: DeliveryAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.RIDER_OPERATIONS)),
):
    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    order = db.scalar(select(Order).where(Order.id == delivery.order_id).with_for_update())
    if delivery.status != DeliveryStatus.UNASSIGNED or order is None or order.status != OrderStatus.READY:
        raise HTTPException(status_code=409, detail="Delivery is no longer available for assignment")
    rider = db.get(User, payload.rider_id)
    if rider is None or rider.role != UserRole.DELIVERY or not rider.is_active or not rider.is_verified:
        raise HTTPException(status_code=422, detail="Select an active verified delivery partner")
    active_delivery = db.scalar(
        select(Delivery.id)
        .where(
            Delivery.delivery_partner_id == rider.id,
            Delivery.status.in_(ACTIVE_DELIVERY_STATUSES),
            Delivery.id != delivery.id,
        )
        .limit(1)
    )
    if active_delivery is not None:
        raise HTTPException(status_code=409, detail="Rider already has an active delivery")
    delivery.delivery_partner_id = rider.id
    transition_delivery(delivery, DeliveryStatus.ASSIGNED)
    delivery.assigned_at = datetime.now(timezone.utc)
    enqueue_notification(db,user_id=order.user_id,event_type="delivery.assigned",title="Delivery partner assigned",body=f"{rider.full_name or 'Your delivery partner'} is assigned to order {order.order_number}.",data={"order_id":str(order.id),"order_number":order.order_number,"delivery_id":str(delivery.id)})
    enqueue_notification(db,user_id=rider.id,event_type="delivery.task_assigned",title="New delivery assigned",body=f"Order {order.order_number} is ready for pickup.",data={"order_id":str(order.id),"order_number":order.order_number,"delivery_id":str(delivery.id)})
    record_admin_action(
        db, request=request, actor=admin, action="delivery.assigned",
        capability=Capability.RIDER_OPERATIONS, resource_type="delivery", resource_id=delivery.id,
        previous_state={"status": DeliveryStatus.UNASSIGNED.value, "delivery_partner_id": None},
        resulting_state={"status": delivery.status.value, "delivery_partner_id": str(rider.id)},
        reason="manual_rider_assignment",
    )
    db.commit()
    db.refresh(delivery)
    return _delivery_payload(db, delivery)


@router.post("/deliveries/{delivery_id}/unassign")
def admin_unassign_delivery(
    delivery_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.RIDER_OPERATIONS)),
):
    delivery = db.scalar(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    if delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if delivery.status != DeliveryStatus.ASSIGNED:
        raise HTTPException(status_code=409, detail="Only a delivery awaiting pickup can be unassigned")
    order = db.scalar(select(Order).where(Order.id == delivery.order_id).with_for_update())
    if order is None:
        raise HTTPException(status_code=409, detail="Delivery order is missing")
    if order.status != OrderStatus.READY:
        raise HTTPException(status_code=409, detail="Only a ready order can be reassigned before pickup")
    rider_id = delivery.delivery_partner_id
    delivery.delivery_partner_id = None
    transition_delivery(delivery, DeliveryStatus.UNASSIGNED)
    delivery.assigned_at = None
    if rider_id:
        enqueue_notification(db,user_id=rider_id,event_type="delivery.task_unassigned",title="Delivery reassigned",body=f"Order {order.order_number} is no longer assigned to you.",data={"order_id":str(order.id),"order_number":order.order_number,"delivery_id":str(delivery.id)})
    enqueue_notification(db,user_id=order.user_id,event_type="delivery.reassignment",title="Delivery partner is being reassigned",body=f"We are assigning another delivery partner to order {order.order_number}.",data={"order_id":str(order.id),"order_number":order.order_number,"delivery_id":str(delivery.id)})
    record_admin_action(
        db, request=request, actor=admin, action="delivery.unassigned",
        capability=Capability.RIDER_OPERATIONS, resource_type="delivery", resource_id=delivery.id,
        previous_state={"status": DeliveryStatus.ASSIGNED.value, "delivery_partner_id": str(rider_id) if rider_id else None},
        resulting_state={"status": delivery.status.value, "delivery_partner_id": None},
        reason="manual_rider_unassignment",
    )
    db.commit()
    db.refresh(delivery)
    return _delivery_payload(db, delivery)


@router.get("/overview")
def admin_overview(
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.ORDER_READ)),
) -> dict:
    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    village_count = db.scalar(select(func.count()).select_from(Village).where(Village.is_active.is_(True))) or 0
    active_store_count = db.scalar(select(func.count()).select_from(Store).where(Store.is_active.is_(True))) or 0
    pending_merchants = db.scalar(select(func.count()).select_from(Merchant).where(Merchant.status == MerchantStatus.PENDING)) or 0
    approved_merchants = db.scalar(select(func.count()).select_from(Merchant).where(Merchant.status == MerchantStatus.APPROVED)) or 0
    suspended_merchants = db.scalar(select(func.count()).select_from(Merchant).where(Merchant.status == MerchantStatus.SUSPENDED)) or 0
    delivery_users = db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.DELIVERY, User.is_active.is_(True))) or 0
    total_orders = db.scalar(select(func.count()).select_from(Order)) or 0
    can_read_financials = has_capability(admin, Capability.PAYMENT_READ)
    paid_gmv = None
    gross_order_value = None
    if can_read_financials:
        paid_gmv = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.payment_status == PaymentStatus.PAID)) or Decimal("0")
        gross_order_value = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != OrderStatus.CANCELLED)) or Decimal("0")
    low_stock = db.scalar(select(func.count()).select_from(StoreProduct).where(StoreProduct.stock_quantity <= 5, StoreProduct.is_available.is_(True))) or 0
    ready_unassigned = db.scalar(select(func.count()).select_from(Delivery).join(Order, Delivery.order_id == Order.id).where(Delivery.status == DeliveryStatus.UNASSIGNED, Order.status == OrderStatus.READY)) or 0
    grouped = db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all()
    orders_by_status = {status.value: count for status, count in grouped}
    for order_status in OrderStatus:
        orders_by_status.setdefault(order_status.value, 0)
    return {"users":user_count,"villages":village_count,"active_stores":active_store_count,"merchants":{"pending":pending_merchants,"approved":approved_merchants,"suspended":suspended_merchants},"orders":{"total":total_orders,"by_status":orders_by_status},"operations":{"low_stock_listings":low_stock,"ready_unassigned_deliveries":ready_unassigned,"active_delivery_partners":delivery_users},"financials_visible":can_read_financials,"paid_gmv":str(paid_gmv) if paid_gmv is not None else None,"gross_order_value":str(gross_order_value) if gross_order_value is not None else None}


@router.get("/delivery-performance")
def admin_delivery_performance(
    window_days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.RIDER_READ)),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = db.scalars(select(Delivery).where(Delivery.updated_at >= since)).all()
    performance = summarize_delivery_performance(rows)
    return {
        "window_days": window_days,
        "total_records": len(rows),
        "delivered": performance.sample_count,
        "failed": sum(delivery.status == DeliveryStatus.FAILED for delivery in rows),
        "active": sum(delivery.status in ACTIVE_DELIVERY_STATUSES for delivery in rows),
        "median_assignment_to_pickup_seconds": performance.median_assignment_to_pickup_seconds,
        "median_pickup_to_delivery_seconds": performance.median_pickup_to_delivery_seconds,
        "basis": "recorded_delivery_timestamps",
    }
