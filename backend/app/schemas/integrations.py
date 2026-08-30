import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DeviceRegistrationCreate(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    platform: str = Field(pattern="^(android|ios|web)$")
    app_version: str | None = Field(default=None, max_length=40)


class DeviceRegistrationRead(DeviceRegistrationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NotificationConfigResponse(BaseModel):
    enabled: bool
    provider: str = "firebase"


class NotificationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    event_type: str
    title: str
    body: str
    data: dict
    status: str
    created_at: datetime
    sent_at: datetime | None = None


class PaymentConfigResponse(BaseModel):
    enabled: bool
    provider: str
    key_id: str | None = None
    currency: str = "INR"


class PaymentIntentResponse(BaseModel):
    payment_attempt_id: uuid.UUID
    provider: str
    provider_order_id: str
    amount_subunits: int
    amount: Decimal
    currency: str
    key_id: str


class PaymentVerifyRequest(BaseModel):
    payment_attempt_id: uuid.UUID
    razorpay_payment_id: str = Field(min_length=5, max_length=120)
    razorpay_signature: str = Field(min_length=32, max_length=256)


class PaymentVerifyResponse(BaseModel):
    order_id: uuid.UUID
    payment_status: str
    provider_payment_id: str


class PaymentRefundRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    reason: str
    provider_refund_id: str | None = None
    provider_status: str | None = None
    failure_reason: str | None = None
    attempt_count: int
    requested_at: datetime
    processed_at: datetime | None = None
    failed_at: datetime | None = None
