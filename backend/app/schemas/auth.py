from pydantic import BaseModel, Field, field_validator

from app.core.phone import normalize_indian_phone


class OTPRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=20)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_indian_phone(value)


class OTPRequestResponse(BaseModel):
    message: str
    dev_otp: str | None = None
    expires_in_seconds: int | None = None
    resend_after_seconds: int | None = None
    request_limit: int
    request_window_seconds: int


class OTPVerifyRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    otp: str = Field(min_length=4, max_length=8)
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_indian_phone(value)


class WidgetTokenExchangeRequest(BaseModel):
    access_token: str = Field(min_length=20, max_length=4096)
    full_name: str | None = Field(default=None, max_length=120)


class FirebaseTokenExchangeRequest(BaseModel):
    id_token: str = Field(min_length=20, max_length=16384)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
