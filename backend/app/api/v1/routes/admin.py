from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.commerce import Merchant, MerchantStatus, Store, StoreProduct
from app.models.geography import Village
from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus, PaymentStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin", tags=["Admin"])

class UserRoleUpdate(BaseModel):
    role: UserRole
    is_active: bool = True

@router.get("/users")
def admin_users(db:Session=Depends(get_db), _:User=Depends(require_roles(UserRole.ADMIN))):
    users=db.scalars(select(User).order_by(User.created_at.desc()).limit(500)).all()
    return [{"id":str(u.id),"phone":u.phone,"full_name":u.full_name,"role":u.role.value,"is_active":u.is_active,"is_verified":u.is_verified,"created_at":u.created_at} for u in users]

@router.patch("/users/{user_id}/role")
def admin_update_user(user_id:uuid.UUID,payload:UserRoleUpdate,db:Session=Depends(get_db),admin:User=Depends(require_roles(UserRole.ADMIN))):
    user=db.get(User,user_id)
    if user is None: raise HTTPException(status_code=404,detail="User not found")
    if user.id==admin.id and payload.role!=UserRole.ADMIN: raise HTTPException(status_code=400,detail="You cannot remove your own admin role")
    user.role=payload.role; user.is_active=payload.is_active; user.is_verified=True; db.commit(); db.refresh(user)
    return {"id":str(user.id),"phone":user.phone,"full_name":user.full_name,"role":user.role.value,"is_active":user.is_active,"is_verified":user.is_verified,"created_at":user.created_at}

@router.get("/overview")
def admin_overview(db:Session=Depends(get_db),_:User=Depends(require_roles(UserRole.ADMIN)))->dict:
    user_count=db.scalar(select(func.count()).select_from(User)) or 0
    village_count=db.scalar(select(func.count()).select_from(Village).where(Village.is_active.is_(True))) or 0
    active_store_count=db.scalar(select(func.count()).select_from(Store).where(Store.is_active.is_(True))) or 0
    pending_merchants=db.scalar(select(func.count()).select_from(Merchant).where(Merchant.status==MerchantStatus.PENDING)) or 0
    approved_merchants=db.scalar(select(func.count()).select_from(Merchant).where(Merchant.status==MerchantStatus.APPROVED)) or 0
    suspended_merchants=db.scalar(select(func.count()).select_from(Merchant).where(Merchant.status==MerchantStatus.SUSPENDED)) or 0
    delivery_users=db.scalar(select(func.count()).select_from(User).where(User.role==UserRole.DELIVERY,User.is_active.is_(True))) or 0
    total_orders=db.scalar(select(func.count()).select_from(Order)) or 0
    paid_gmv=db.scalar(select(func.coalesce(func.sum(Order.total),0)).where(Order.payment_status==PaymentStatus.PAID)) or Decimal("0")
    gross_order_value=db.scalar(select(func.coalesce(func.sum(Order.total),0)).where(Order.status!=OrderStatus.CANCELLED)) or Decimal("0")
    low_stock=db.scalar(select(func.count()).select_from(StoreProduct).where(StoreProduct.stock_quantity<=5,StoreProduct.is_available.is_(True))) or 0
    ready_unassigned=db.scalar(select(func.count()).select_from(Delivery).join(Order,Delivery.order_id==Order.id).where(Delivery.status==DeliveryStatus.UNASSIGNED,Order.status==OrderStatus.READY)) or 0
    grouped=db.execute(select(Order.status,func.count(Order.id)).group_by(Order.status)).all(); orders_by_status={s.value:c for s,c in grouped}
    for s in OrderStatus: orders_by_status.setdefault(s.value,0)
    return {"users":user_count,"villages":village_count,"active_stores":active_store_count,"merchants":{"pending":pending_merchants,"approved":approved_merchants,"suspended":suspended_merchants},"orders":{"total":total_orders,"by_status":orders_by_status},"operations":{"low_stock_listings":low_stock,"ready_unassigned_deliveries":ready_unassigned,"active_delivery_partners":delivery_users},"paid_gmv":str(paid_gmv),"gross_order_value":str(gross_order_value)}
