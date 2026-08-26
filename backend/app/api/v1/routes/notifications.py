import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.integrations import DeviceRegistration, NotificationEvent
from app.models.user import User
from app.schemas.integrations import (
    DeviceRegistrationCreate,
    DeviceRegistrationRead,
    NotificationConfigResponse,
    NotificationEventRead,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/config", response_model=NotificationConfigResponse)
def notification_config() -> NotificationConfigResponse:
    return NotificationConfigResponse(enabled=bool(settings.FCM_PROJECT_ID))


@router.post(
    "/devices",
    response_model=DeviceRegistrationRead,
    status_code=status.HTTP_201_CREATED,
)
def register_device(
    payload: DeviceRegistrationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    registration = db.scalar(
        select(DeviceRegistration).where(DeviceRegistration.token == payload.token)
    )
    if registration is None:
        registration = DeviceRegistration(user_id=user.id, **payload.model_dump())
        db.add(registration)
    else:
        registration.user_id = user.id
        registration.platform = payload.platform
        registration.app_version = payload.app_version
        registration.is_active = True
    db.commit()
    db.refresh(registration)
    return registration


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device(
    device_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    registration = db.get(DeviceRegistration, device_id)
    if registration is None or registration.user_id != user.id:
        raise HTTPException(status_code=404, detail="Device registration not found")
    registration.is_active = False
    db.commit()


@router.get("/me", response_model=list[NotificationEventRead])
def my_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return db.scalars(
        select(NotificationEvent)
        .where(NotificationEvent.user_id == user.id)
        .order_by(NotificationEvent.created_at.desc())
        .limit(limit)
    ).all()
