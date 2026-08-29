import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RiderPresence(Base):
    __tablename__ = "rider_presences"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_rider_presence_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_rider_presence_longitude"),
    )

    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
