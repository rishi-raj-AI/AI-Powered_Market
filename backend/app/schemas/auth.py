from pydantic import BaseModel, Field


class OTPRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=20)


class OTPRequestResponse(BaseModel):
    message: str
    dev_otp: str | None = None


class OTPVerifyRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    otp: str = Field(min_length=4, max_length=8)
    full_name: str | None = Field(default=None, max_length=120)


class WidgetTokenExchangeRequest(BaseModel):
    access_token: str = Field(min_length=20, max_length=4096)
    full_name: str | None = Field(default=None, max_length=120)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
