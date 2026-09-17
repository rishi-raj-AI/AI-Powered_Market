"""Add listing-owned product-media lifecycle, jobs and audit records.

Revision ID: 0023_product_media_foundation
Revises: 0022_template_store_banners
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0023_product_media_foundation"
down_revision: Union[str, None] = "0022_template_store_banners"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_media_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploader_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="quarantined"),
        sa.Column("source_object_key", sa.String(512), nullable=False, unique=True),
        sa.Column("public_object_key", sa.String(512), unique=True),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("derivative_sha256", sa.String(64)),
        sa.Column("detected_mime", sa.String(64)),
        sa.Column("byte_size", sa.Integer()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("alt_text", sa.String(240)),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("processing_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.Column("purge_after_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('quarantined', 'processing', 'approved', 'rejected', 'retired', 'disabled', 'purge_failed')", name="ck_product_media_assets_state"),
        sa.CheckConstraint("position >= 0", name="ck_product_media_assets_position"),
        sa.CheckConstraint("processing_attempt_count >= 0", name="ck_product_media_assets_attempt_count"),
        sa.CheckConstraint("byte_size IS NULL OR byte_size > 0", name="ck_product_media_assets_byte_size"),
        sa.CheckConstraint("char_length(source_sha256) = 64", name="ck_product_media_assets_source_sha"),
        sa.CheckConstraint("derivative_sha256 IS NULL OR char_length(derivative_sha256) = 64", name="ck_product_media_assets_derivative_sha"),
        sa.CheckConstraint("width IS NULL OR width > 0", name="ck_product_media_assets_width"),
        sa.CheckConstraint("height IS NULL OR height > 0", name="ck_product_media_assets_height"),
        sa.CheckConstraint("NOT is_primary OR state = 'approved'", name="ck_product_media_assets_primary_approved"),
        sa.CheckConstraint("state != 'approved' OR public_object_key IS NOT NULL", name="ck_product_media_assets_approved_key"),
    )
    for column in ("store_product_id", "uploader_user_id", "state", "source_sha256", "next_attempt_at", "lease_expires_at", "purge_after_at"):
        op.create_index(f"ix_product_media_assets_{column}", "product_media_assets", [column])
    op.create_index(
        "uq_product_media_assets_active_position",
        "product_media_assets",
        ["store_product_id", "position"],
        unique=True,
        postgresql_where=sa.text("state NOT IN ('retired', 'purge_failed')"),
    )
    op.create_index(
        "uq_product_media_assets_approved_primary",
        "product_media_assets",
        ["store_product_id"],
        unique=True,
        postgresql_where=sa.text("is_primary AND state = 'approved'"),
    )

    op.create_table(
        "product_media_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_media_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("asset_id", name="uq_product_media_job_asset"),
        sa.CheckConstraint("state IN ('queued', 'processing', 'retrying', 'succeeded', 'failed')", name="ck_product_media_jobs_state"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_product_media_jobs_attempt_count"),
    )
    for column in ("state", "next_attempt_at", "lease_expires_at", "created_at"):
        op.create_index(f"ix_product_media_jobs_{column}", "product_media_jobs", [column])

    op.create_table(
        "product_media_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_media_assets.id", ondelete="SET NULL")),
        sa.Column("store_product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("store_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("reason_code", sa.String(80)),
        sa.Column("event_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("request_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("asset_id", "store_product_id", "actor_user_id", "action", "request_id", "created_at"):
        op.create_index(f"ix_product_media_audit_events_{column}", "product_media_audit_events", [column])


def downgrade() -> None:
    op.drop_table("product_media_audit_events")
    op.drop_table("product_media_jobs")
    op.drop_table("product_media_assets")
