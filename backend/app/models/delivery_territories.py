"""Additive delivery territory entities; legacy service areas remain authoritative.

Do not query these tables for checkout until migration/backfill, comparison-mode
validation, publication controls and a separately reviewed feature-flag switch.
PostGIS polygon columns are restricted to SRID 4326 multipolygons.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.db.base import Base


class MultiPolygon4326(UserDefinedType):
    """PostGIS geometry without an additional ORM dependency."""

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "geometry(MULTIPOLYGON,4326)"


class OperatingRegion(Base):
    __tablename__ = "operating_regions"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'inactive')", name="ck_operating_regions_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    state_code: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class DeliveryHub(Base):
    __tablename__ = "delivery_hubs"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_delivery_hubs_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_delivery_hubs_longitude"),
        CheckConstraint("status IN ('draft', 'active', 'inactive')", name="ck_delivery_hubs_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operating_region_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("operating_regions.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DeliveryTerritory(Base):
    __tablename__ = "delivery_territories"
    __table_args__ = (
        CheckConstraint("geometry_type IN ('circle', 'polygon')", name="ck_delivery_territories_type"),
        CheckConstraint("status IN ('draft', 'active', 'inactive')", name="ck_delivery_territories_status"),
        CheckConstraint("center_latitude IS NULL OR center_latitude BETWEEN -90 AND 90", name="ck_delivery_territories_latitude"),
        CheckConstraint("center_longitude IS NULL OR center_longitude BETWEEN -180 AND 180", name="ck_delivery_territories_longitude"),
        CheckConstraint("(center_latitude IS NULL) = (center_longitude IS NULL)", name="ck_delivery_territories_center_pair"),
        CheckConstraint("radius_km IS NULL OR radius_km > 0", name="ck_delivery_territories_radius"),
        CheckConstraint("effective_until IS NULL OR effective_from IS NULL OR effective_until > effective_from", name="ck_delivery_territories_dates"),
        CheckConstraint("geometry IS NULL OR ST_IsValid(geometry)", name="ck_delivery_territories_valid_geom"),
        Index("ix_delivery_territories_geometry_gist", "geometry", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operating_region_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("operating_regions.id"), nullable=False, index=True)
    hub_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("delivery_hubs.id"), index=True)
    legacy_service_area_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("service_areas.id"), unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    geometry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    geometry: Mapped[Any | None] = mapped_column(MultiPolygon4326(), nullable=True)
    center_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    center_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    radius_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class DeliveryTerritoryExclusion(Base):
    __tablename__ = "delivery_territory_exclusions"
    __table_args__ = (
        CheckConstraint("ST_IsValid(geometry)", name="ck_delivery_territory_exclusions_valid_geom"),
        Index("ix_delivery_territory_exclusions_geometry_gist", "geometry", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    territory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("delivery_territories.id"), nullable=False, index=True)
    geometry: Mapped[Any] = mapped_column(MultiPolygon4326(), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StoreDeliveryTerritory(Base):
    __tablename__ = "store_delivery_territories"
    __table_args__ = (
        UniqueConstraint("store_id", "territory_id", name="uq_store_delivery_territory"),
        CheckConstraint("status IN ('draft', 'active', 'inactive')", name="ck_store_delivery_territories_status"),
        CheckConstraint("effective_until IS NULL OR effective_from IS NULL OR effective_until > effective_from", name="ck_store_delivery_territories_dates"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False, index=True)
    territory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("delivery_territories.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    delivery_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DeliveryTerritoryVersion(Base):
    __tablename__ = "delivery_territory_versions"
    __table_args__ = (
        UniqueConstraint("territory_id", "version", name="uq_delivery_territory_version"),
        CheckConstraint("version > 0", name="ck_delivery_territory_versions_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    territory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("delivery_territories.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TerritoryChangeAudit(Base):
    __tablename__ = "territory_change_audit"
    __table_args__ = (
        CheckConstraint("action IN ('draft_created', 'draft_edited', 'published', 'rolled_back', 'store_assigned', 'store_unassigned')", name="ck_territory_change_audit_action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    territory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("delivery_territories.id"), nullable=False, index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_version: Mapped[int | None] = mapped_column(Integer)
    new_version: Mapped[int | None] = mapped_column(Integer)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
