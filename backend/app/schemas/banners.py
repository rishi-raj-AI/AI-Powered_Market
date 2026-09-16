from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BannerManifest(BaseModel):
    """Closed presentation data rendered by first-party clients only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: Literal["gaonone-store-locality-v1"]
    template_revision: Literal["v1"]
    title: str = Field(min_length=1, max_length=160)
    locality: str = Field(min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=100)


class BannerPresentationRead(BannerManifest):
    """The only banner shape available on public storefront reads."""


class BannerVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    version: int
    generation_status: Literal["queued", "processing", "retrying", "ready", "failed"]
    moderation_status: Literal["pending", "approved", "rejected", "disabled"]
    manifest: BannerManifest | None = None
    failure_code: str | None = None
    created_at: datetime
    ready_at: datetime | None = None
    moderated_at: datetime | None = None


class BannerSelectionRead(BaseModel):
    store_id: uuid.UUID
    revision: int
    active_version_id: uuid.UUID | None = None
    active_banner: BannerPresentationRead | None = None
    versions: list[BannerVersionRead]


class BannerRegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class BannerGenerationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    version_id: uuid.UUID
    status: Literal["queued", "processing", "retrying", "succeeded", "failed"]
    attempt_count: int
    next_attempt_at: datetime | None = None
    created_at: datetime


class BannerAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_revision: int = Field(ge=0)


class BannerModerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject", "disable"]
    reason_code: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9_:-]+$")
