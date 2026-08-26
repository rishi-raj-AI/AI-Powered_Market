import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

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
