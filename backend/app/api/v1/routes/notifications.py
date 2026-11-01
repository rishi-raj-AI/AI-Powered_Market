import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_capability
from app.core.capabilities import Capability
from app.core.config import settings
from app.models.integrations import DeviceRegistration, NotificationEvent
from app.models.user import User
from app.schemas.integrations import DeviceRegistrationCreate, DeviceRegistrationRead, NotificationConfigResponse, NotificationEventRead
from app.services.fcm import flush_pending

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/config", response_model=NotificationConfigResponse)
def notification_config() -> NotificationConfigResponse:
    # Do not advertise push as enabled when the worker lacks credentials.
    # A configured project ID alone cannot deliver any notification.
    return NotificationConfigResponse(enabled=bool(settings.FCM_PROJECT_ID and settings.FCM_SERVICE_ACCOUNT_JSON_B64))

@router.post("/devices", response_model=DeviceRegistrationRead, status_code=status.HTTP_201_CREATED)
def register_device(payload: DeviceRegistrationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Serialize registration changes for an existing token. An active token
    # already owned by another account must not be hijacked by someone who
    # learned its value; shared devices rotate tokens on logout.
    registration = db.scalar(
        select(DeviceRegistration)
        .where(DeviceRegistration.token == payload.token)
        .with_for_update()
    )
    if registration is None:
        registration = DeviceRegistration(user_id=user.id, **payload.model_dump())
        db.add(registration)
    else:
        if registration.is_active and registration.user_id != user.id:
            raise HTTPException(
                status_code=409,
                detail="Device token is already active for another account",
            )
        # Inactive tokens can be reclaimed after logout. The same user can
        # idempotently refresh metadata or reactivate their own registration.
        registration.user_id = user.id
        registration.platform = payload.platform
        registration.app_version = payload.app_version
        registration.is_active = True
    try:
        db.commit()
    except IntegrityError as exc:
        # Two concurrent first registrations can both observe no row. The
        # unique token constraint resolves the race without a 500 response.
        db.rollback()
        raise HTTPException(status_code=409, detail="Device token registration conflict") from exc
    db.refresh(registration)
    return registration

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
def flush_notifications(
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.NOTIFICATION_OPERATIONS)),
):
    return flush_pending(db)
