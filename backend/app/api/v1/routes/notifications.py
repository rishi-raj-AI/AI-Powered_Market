import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.core.config import settings
from app.models.integrations import DeviceRegistration, NotificationEvent
from app.models.user import User, UserRole
from app.schemas.integrations import DeviceRegistrationCreate, DeviceRegistrationRead, NotificationConfigResponse, NotificationEventRead
from app.services.fcm import flush_pending

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/config", response_model=NotificationConfigResponse)
def notification_config() -> NotificationConfigResponse:
    return NotificationConfigResponse(enabled=bool(settings.FCM_PROJECT_ID))

@router.post("/devices", response_model=DeviceRegistrationRead, status_code=status.HTTP_201_CREATED)
def register_device(payload: DeviceRegistrationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    registration = db.scalar(select(DeviceRegistration).where(DeviceRegistration.token == payload.token))
    if registration is None:
        registration = DeviceRegistration(user_id=user.id, **payload.model_dump()); db.add(registration)
    else:
        # Rebinding is deliberate: a device token identifies a handset, and when
        # a different person signs in on that handset the registration must
        # follow them or they get no notifications. token is uniquely
        # constrained, so there can only ever be one owner. This does mean a
        # stolen token could be re-registered to divert that handset's pushes;
        # the token is only ever known to the device and the server, and the
        # alternative (refusing the rebind) breaks the normal handover case.
        registration.user_id=user.id; registration.platform=payload.platform; registration.app_version=payload.app_version; registration.is_active=True
    db.commit(); db.refresh(registration); return registration

@router.get("/devices", response_model=list[DeviceRegistrationRead])
def my_devices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(DeviceRegistration).where(DeviceRegistration.user_id == user.id, DeviceRegistration.is_active.is_(True)).order_by(DeviceRegistration.updated_at.desc())).all()

@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device(device_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    registration=db.get(DeviceRegistration,device_id)
    if registration is None or registration.user_id != user.id: raise HTTPException(status_code=404,detail="Device registration not found")
    registration.is_active=False; db.commit()

@router.get("/me", response_model=list[NotificationEventRead])
def my_notifications(limit:int=Query(default=50,ge=1,le=100), db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    return db.scalars(select(NotificationEvent).where(NotificationEvent.user_id==user.id).order_by(NotificationEvent.created_at.desc()).limit(limit)).all()

@router.post("/flush")
def flush_notifications(db:Session=Depends(get_db), _:User=Depends(require_roles(UserRole.ADMIN))):
    return flush_pending(db)
