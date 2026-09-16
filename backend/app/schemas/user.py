import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    full_name: str | None
    role: UserRole
    is_super_admin: bool
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class CapabilityResponse(BaseModel):
    is_super_admin: bool
    capabilities: list[str]


class UserProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned
