from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    OTPRequest,
    OTPRequestResponse,
    OTPVerifyRequest,
    TokenResponse,
    WidgetTokenExchangeRequest,
)
from app.services.msg91_widget import verify_widget_access_token
from app.services.otp import otp_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _login_verified_phone(phone: str, full_name: str | None, db: Session) -> TokenResponse:
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, full_name=full_name, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
        if full_name and not user.full_name:
            user.full_name = full_name
        user.is_verified = True
        db.commit()
        db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/request-otp", response_model=OTPRequestResponse)
def request_otp(payload: OTPRequest) -> OTPRequestResponse:
    if settings.APP_ENV == "production" and settings.AUTH_PROVIDER == "msg91_widget":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Production OTP is handled by the MSG91 widget",
        )
    try:
        result = otp_service.issue(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return OTPRequestResponse(message=result.message, dev_otp=result.dev_otp)


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if settings.APP_ENV == "production" and settings.AUTH_PROVIDER == "msg91_widget":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Production OTP is handled by the MSG91 widget",
        )
    if not otp_service.verify(payload.phone, payload.otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    return _login_verified_phone(payload.phone, payload.full_name, db)


@router.post("/widget/exchange", response_model=TokenResponse)
def exchange_widget_token(
    payload: WidgetTokenExchangeRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    if settings.AUTH_PROVIDER != "msg91_widget":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget authentication is disabled")
    try:
        identity = verify_widget_access_token(payload.access_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return _login_verified_phone(identity.identifier, payload.full_name, db)
