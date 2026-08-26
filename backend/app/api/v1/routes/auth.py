from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import OTPRequest, OTPRequestResponse, OTPVerifyRequest, TokenResponse
from app.services.otp import otp_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/request-otp", response_model=OTPRequestResponse)
def request_otp(payload: OTPRequest) -> OTPRequestResponse:
    try:
        result = otp_service.issue(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return OTPRequestResponse(message=result.message, dev_otp=result.dev_otp)


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if not otp_service.verify(payload.phone, payload.otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None:
        user = User(phone=payload.phone, full_name=payload.full_name, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
        if payload.full_name and not user.full_name:
            user.full_name = payload.full_name
        user.is_verified = True
        db.commit()
        db.refresh(user)

    return TokenResponse(access_token=create_access_token(str(user.id)))
