import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.orders import DeliveryStatus, OrderStatus, PaymentMethod, PaymentStatus


class CartItemUpsert(BaseModel):
    store_product_id: uuid.UUID
    quantity: int = Field(ge=1, le=99)


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    store_product_id: uuid.UUID
    quantity: int


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
    updated_at: datetime


class DeliveryStatusUpdate(BaseModel):
    status: DeliveryStatus
