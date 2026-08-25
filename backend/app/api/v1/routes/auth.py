from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import OTPRequest, OTPRequestResponse, OTPVerifyRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
DEV_OTP = "123456"


@router.post("/request-otp", response_model=OTPRequestResponse)
def request_otp(payload: OTPRequest) -> OTPRequestResponse:
    if settings.APP_ENV != "development":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SMS OTP provider is not configured yet",
        )
    return OTPRequestResponse(message="Development OTP generated", dev_otp=DEV_OTP)


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if settings.APP_ENV != "development":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="SMS OTP provider is not configured yet",
        )
    if payload.otp != DEV_OTP:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        user = User(phone=payload.phone, full_name=payload.full_name, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if payload.full_name and not user.full_name:
            user.full_name = payload.full_name
        user.is_verified = True
        db.commit()
        db.refresh(user)

    return TokenResponse(access_token=create_access_token(str(user.id)))
