"""Add durable template-store banner candidates, jobs, selections and audit evidence.

Revision ID: 0022_template_store_banners
Revises: 0021_normalize_user_phones
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0022_template_store_banners"
down_revision: Union[str, None] = "0021_normalize_user_phones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "store_banner_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="template"),
        sa.Column("template_revision", sa.String(80), nullable=False),
        sa.Column("manifest", sa.JSON()),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("generation_status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("moderation_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("failure_code", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.Column("moderated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "moderated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.UniqueConstraint("store_id", "version", name="uq_store_banner_version"),
        sa.CheckConstraint("source IN ('template')", name="ck_store_banner_versions_source"),
        sa.CheckConstraint(
            "generation_status IN ('queued', 'processing', 'retrying', 'ready', 'failed')",
            name="ck_store_banner_versions_generation_status",
        ),
        sa.CheckConstraint(
            "moderation_status IN ('pending', 'approved', 'rejected', 'disabled')",
            name="ck_store_banner_versions_moderation_status",
        ),
    )
    for column in (
        "store_id",
        "input_fingerprint",
        "generation_status",
        "moderation_status",
        "moderated_by_user_id",
    ):
        op.create_index(f"ix_store_banner_versions_{column}", "store_banner_versions", [column])

    op.create_table(
        "banner_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("store_banner_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("store_id", "idempotency_key", name="uq_banner_job_store_idempotency"),
        sa.UniqueConstraint("version_id", name="uq_banner_job_version"),
        sa.CheckConstraint(
            "trigger IN ('store_created', 'merchant_regenerate')",
            name="ck_banner_generation_jobs_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'retrying', 'succeeded', 'failed')",
            name="ck_banner_generation_jobs_status",
        ),
    )
    for column in ("store_id", "status", "next_attempt_at", "lease_expires_at", "created_at"):
        op.create_index(f"ix_banner_generation_jobs_{column}", "banner_generation_jobs", [column])

    op.create_table(
        "store_banner_selections",
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "active_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("store_banner_versions.id", ondelete="SET NULL"),
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "selected_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    for column in ("active_version_id", "selected_by_user_id"):
        op.create_index(f"ix_store_banner_selections_{column}", "store_banner_selections", [column])

    op.create_table(
        "banner_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("store_banner_versions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("reason_code", sa.String(80)),
        sa.Column("request_id", sa.String(160), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    for column in ("store_id", "version_id", "actor_user_id", "action", "request_id", "created_at"):
        op.create_index(f"ix_banner_audit_events_{column}", "banner_audit_events", [column])


def downgrade() -> None:
    op.drop_table("banner_audit_events")
    op.drop_table("store_banner_selections")
    op.drop_table("banner_generation_jobs")
    op.drop_table("store_banner_versions")
