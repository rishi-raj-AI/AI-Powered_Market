from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import ExternalIdentity, User
from app.schemas.auth import (
    OTPRequest,
    OTPRequestResponse,
    OTPVerifyRequest,
    FirebaseTokenExchangeRequest,
    TokenResponse,
    WidgetTokenExchangeRequest,
)
from app.services.msg91_widget import verify_widget_access_token
from app.services.otp import otp_service
from app.services.firebase_auth import FirebaseTokenInvalid, FirebaseVerifierUnavailable, firebase_token_verifier

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _login_verified_phone(phone: str, full_name: str | None, db: Session) -> TokenResponse:
    full_name = " ".join(full_name.split()) if full_name and full_name.strip() else None
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, full_name=full_name, is_verified=True)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            # A concurrent verification of the same canonical phone may have
            # created the identity first. Never create or merge a second user.
            db.rollback()
            user = db.scalar(select(User).where(User.phone == phone))
            if user is None:
                raise
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    if full_name and not user.full_name:
        user.full_name = full_name
    user.is_verified = True
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


def _login_firebase_identity(subject: str, display_name: str | None, db: Session) -> TokenResponse:
    """Resolve an immutable Firebase subject without email-based account takeover."""
    if not subject.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firebase token did not contain a subject")
    identity = db.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == "firebase",
            ExternalIdentity.subject == subject,
        )
    )
    if identity is None:
        user = User(phone=None, full_name=display_name, is_verified=True)
        db.add(user)
        db.flush()
        identity = ExternalIdentity(user_id=user.id, provider="firebase", subject=subject)
        db.add(identity)
        try:
            db.commit()
        except IntegrityError:
            # A concurrent exchange for this provider subject won the race.
            # Never create a second account or infer an email-based match.
            db.rollback()
            identity = db.scalar(
                select(ExternalIdentity).where(
                    ExternalIdentity.provider == "firebase",
                    ExternalIdentity.subject == subject,
                )
            )
            if identity is None:
                raise
    user = db.get(User, identity.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is unavailable")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    identity.last_authenticated_at = datetime.now(timezone.utc)
    db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


def _sms_routes_enabled() -> bool:
    return settings.SMS_AUTH_ENABLED and settings.AUTH_PROVIDER == "local_otp"


@router.post("/request-otp", response_model=OTPRequestResponse)
def request_otp(payload: OTPRequest) -> OTPRequestResponse:
    if not _sms_routes_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SMS authentication is disabled",
        )
    try:
        result = otp_service.issue(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return OTPRequestResponse(
        message=result.message,
        dev_otp=result.dev_otp,
        expires_in_seconds=result.expires_in_seconds,
        resend_after_seconds=None,
        request_limit=settings.OTP_MAX_REQUESTS_PER_WINDOW,
        request_window_seconds=settings.OTP_RATE_WINDOW_SECONDS,
    )


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if not _sms_routes_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SMS authentication is disabled",
        )
    try:
        verified = otp_service.verify(payload.phone, payload.otp)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if not verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    return _login_verified_phone(payload.phone, payload.full_name, db)


@router.post("/widget/exchange", response_model=TokenResponse)
def exchange_widget_token(
    payload: WidgetTokenExchangeRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    if not settings.SMS_AUTH_ENABLED or settings.AUTH_PROVIDER != "msg91_widget":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget authentication is disabled")
    try:
        identity = verify_widget_access_token(payload.access_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return _login_verified_phone(identity.identifier, payload.full_name, db)


@router.post("/firebase/exchange", response_model=TokenResponse)
def exchange_firebase_token(
    payload: FirebaseTokenExchangeRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    if settings.AUTH_PROVIDER != "firebase":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firebase authentication is disabled")
    try:
        identity = firebase_token_verifier.verify(payload.id_token)
    except FirebaseTokenInvalid as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except FirebaseVerifierUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return _login_firebase_identity(identity.subject, identity.display_name, db)
