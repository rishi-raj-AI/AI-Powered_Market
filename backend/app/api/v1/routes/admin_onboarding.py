"""Audited pre-registration: no password, session or verification bypass."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_capability
from app.core.capabilities import Capability
from app.models.user import User, UserRole
from app.services.governance_audit import record_admin_action

router = APIRouter(prefix="/admin", tags=["Admin"])


class UserOnboardRequest(BaseModel):
    phone: str = Field(pattern=r"^\\+[1-9][0-9]{7,14}$")
    full_name: str = Field(min_length=2, max_length=120)
    role: UserRole


@router.post("/users/onboard", status_code=201)
def admin_onboard_user(
    payload: UserOnboardRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.ADMIN_MANAGE)),
):
    """Pre-register a user; their own verified phone login is still required."""
    if payload.role == UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrator onboarding requires a verified account")
    if db.scalar(select(User.id).where(User.phone == payload.phone)) is not None:
        raise HTTPException(status_code=409, detail="Phone already registered; manage existing account")
    user = User(phone=payload.phone, full_name=payload.full_name.strip(),
                role=payload.role, is_active=True, is_verified=False)
    db.add(user)
    db.flush()
    record_admin_action(
        db, request=request, actor=admin, action="user.onboarded",
        capability=Capability.ADMIN_MANAGE, resource_type="user", resource_id=user.id,
        previous_state={}, resulting_state={"role": user.role.value, "is_verified": False},
        reason="administrator_pre_registration",
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Phone already registered") from exc
    db.refresh(user)
    return {
        "id": str(user.id), "phone": user.phone, "full_name": user.full_name,
        "role": user.role.value, "is_active": user.is_active,
        "is_verified": user.is_verified, "created_at": user.created_at,
    }
