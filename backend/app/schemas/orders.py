import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.orders import DeliveryStatus, OrderStatus, PaymentMethod, PaymentStatus
from app.schemas.commerce import StoreProductRead


class CartItemUpsert(BaseModel):
    store_product_id: uuid.UUID
    quantity: int = Field(ge=1, le=99)


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    store_product_id: uuid.UUID
    quantity: int
    store_product: StoreProductRead


class CartRead(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID | None
    items: list[CartItemRead]
    subtotal: Decimal


class CheckoutRequest(BaseModel):
    address_id: uuid.UUID
    payment_method: PaymentMethod = PaymentMethod.COD


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_number: str
    user_id: uuid.UUID
    store_id: uuid.UUID
    address_id: uuid.UUID
    status: OrderStatus
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    subtotal: Decimal
    delivery_fee: Decimal
    total: Decimal
    created_at: datetime
    updated_at: datetime


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    unit: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class DeliverySummaryRead(BaseModel):
    id: uuid.UUID
    delivery_partner_id: uuid.UUID | None
    status: DeliveryStatus
    assigned_at: datetime | None
    picked_up_at: datetime | None
    delivered_at: datetime | None
    failed_at: datetime | None = None
    failure_reason: str | None = None


class OrderDetailRead(OrderRead):
    store_name: str
    store_phone: str | None = None
    store_landmark: str | None = None
    recipient_name: str | None = None
    recipient_phone: str | None = None
    house_details: str | None = None
    customer_landmark: str
    customer_directions: str | None = None
    items: list[OrderItemRead]
    delivery: DeliverySummaryRead | None = None


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class DeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_id: uuid.UUID
    delivery_partner_id: uuid.UUID | None
    status: DeliveryStatus
    assigned_at: datetime | None
    picked_up_at: datetime | None
    delivered_at: datetime | None
    failed_at: datetime | None = None
    failure_reason: str | None = None
    failure_notes: str | None = None
    failure_evidence_url: str | None = None
    updated_at: datetime


class DeliveryTaskRead(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    status: DeliveryStatus
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    total: Decimal
    store_name: str
    store_phone: str | None = None
    store_landmark: str | None = None
    store_latitude: float | None = None
    store_longitude: float | None = None
    recipient_name: str | None = None
    recipient_phone: str | None = None
    house_details: str | None = None
    customer_landmark: str
    customer_directions: str | None = None
    customer_latitude: float | None = None
    customer_longitude: float | None = None


class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus

    @field_validator("status")
    @classmethod
    def require_controlled_terminal_endpoints(cls, value: DeliveryStatus) -> DeliveryStatus:
        if value in {DeliveryStatus.DELIVERED, DeliveryStatus.FAILED}:
            raise ValueError("Use the controlled delivery completion or failure endpoint")
        return value


DeliveryFailureReason = Literal[
    "customer_unavailable",
    "address_not_found",
    "vehicle_issue",
    "merchant_issue",
    "unsafe_condition",
    "other",
]


class DeliveryFailureRequest(BaseModel):
    reason: DeliveryFailureReason
    notes: str | None = Field(default=None, max_length=500)
    evidence_url: str | None = Field(default=None, max_length=500)


class DeliveryProofChallengeRead(BaseModel):
    delivery_id: uuid.UUID
    expires_at: datetime


class DeliveryProofSubmit(BaseModel):
    otp: str = Field(pattern=r"^\d{6}$")
    evidence_url: str | None = Field(default=None, max_length=500)
    recipient_name: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=500)


class DeliveryProofRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    delivery_id: uuid.UUID
    otp_expires_at: datetime
    verified_at: datetime | None
    evidence_url: str | None
    recipient_name: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class StatusTransitionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    order_id: uuid.UUID | None
    delivery_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    from_status: str
    to_status: str
    reason: str | None
    event_metadata: dict
    created_at: datetime
