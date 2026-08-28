from __future__ import annotations
import base64,json,logging
from datetime import datetime,timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.integrations import DeviceRegistration,NotificationEvent
logger=logging.getLogger(__name__)
def _firebase():
    if not settings.FCM_PROJECT_ID or not settings.FCM_SERVICE_ACCOUNT_JSON_B64:return None
    try:
        import firebase_admin
        from firebase_admin import credentials,messaging
        if not firebase_admin._apps:
            info=json.loads(base64.b64decode(settings.FCM_SERVICE_ACCOUNT_JSON_B64).decode("utf-8"))
            firebase_admin.initialize_app(credentials.Certificate(info),{"projectId":settings.FCM_PROJECT_ID})
        return messaging
    except Exception:
        logger.exception("FCM initialization failed");return None
def deliver_event(db:Session,event:NotificationEvent)->int:
    messaging=_firebase()
    if messaging is None:event.status="pending" if settings.FCM_PROJECT_ID else "in_app_only";return 0
    devices=db.scalars(select(DeviceRegistration).where(DeviceRegistration.user_id==event.user_id,DeviceRegistration.is_active.is_(True))).all()
    if not devices:event.status="no_devices";return 0
    sent=0;invalid=[];data={str(k):str(v) for k,v in (event.data or {}).items() if v is not None}
    for device in devices:
        try:messaging.send(messaging.Message(notification=messaging.Notification(title=event.title,body=event.body),data=data,token=device.token));sent+=1
        except Exception as exc:
            text=str(exc).lower()
            if "registration-token-not-registered" in text or "not found" in text or "unregistered" in text:invalid.append(device.token)
            else:logger.warning("FCM send failed for event %s: %s",event.id,exc)
    for device in devices:
        if device.token in invalid:device.is_active=False
    event.status="sent" if sent else "failed"
    if sent:event.sent_at=datetime.now(timezone.utc)
    return sent
def flush_pending(db:Session,limit:int=100)->dict[str,int]:
    events=db.scalars(select(NotificationEvent).where(NotificationEvent.status=="pending").order_by(NotificationEvent.created_at).limit(limit)).all();delivered=0
    for event in events:delivered+=deliver_event(db,event)
    db.commit();return {"events":len(events),"pushes":delivered}
