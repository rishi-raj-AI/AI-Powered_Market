import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CodCollectionRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class CodCollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    delivery_id: uuid.UUID
    order_id: uuid.UUID
    amount: Decimal
    collected_by_user_id: uuid.UUID | None
    collected_at: datetime
    created_at: datetime
