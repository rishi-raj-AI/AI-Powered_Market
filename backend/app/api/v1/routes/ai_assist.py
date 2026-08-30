from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_roles
from app.models.user import User, UserRole
from app.services.ai_assist import catalog_draft, parse_order_intent

router = APIRouter(prefix="/ai", tags=["AI Assist"])


class OrderIntentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    language: Literal["en", "hi", "mr"] | None = None
    input_mode: Literal["text", "voice_transcript"] = "text"


class CatalogAssistRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    language: Literal["en", "hi", "mr"] | None = None


@router.post("/order-intent")
def order_intent(
    payload: OrderIntentRequest,
    _: User = Depends(get_current_user),
) -> dict:
    result = parse_order_intent(payload.text, payload.language)
    result["input_mode"] = payload.input_mode
    result["source"] = "deterministic_multilingual_parser"
    return result


@router.post("/catalog-assist")
def merchant_catalog_assist(
    payload: CatalogAssistRequest,
    _: User = Depends(require_roles(UserRole.MERCHANT, UserRole.ADMIN)),
) -> dict:
    result = catalog_draft(payload.name, payload.description, payload.language)
    result["source"] = "deterministic_catalog_assistant"
    return result
