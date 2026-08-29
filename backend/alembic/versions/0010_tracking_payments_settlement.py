"""Add durable payment webhook and settlement ledger support.

Revision ID: 0010_tracking_payments_settlement
Revises: 0009_postgis_dispatch
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_tracking_payments_settlement"
down_revision = "0009_postgis_dispatch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("event_key", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("provider", "event_key", name="uq_payment_webhook_provider_event"),
    )
    op.create_index("ix_payment_webhook_events_created_at", "payment_webhook_events", ["created_at"])

    op.create_table(
        "settlement_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("gross_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("merchant_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("delivery_fee_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_settlement_entries_merchant_id", "settlement_entries", ["merchant_id"])
    op.create_index("ix_settlement_entries_status", "settlement_entries", ["status"])
    op.create_index("ix_settlement_entries_created_at", "settlement_entries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_settlement_entries_created_at", table_name="settlement_entries")
    op.drop_index("ix_settlement_entries_status", table_name="settlement_entries")
    op.drop_index("ix_settlement_entries_merchant_id", table_name="settlement_entries")
    op.drop_table("settlement_entries")
    op.drop_index("ix_payment_webhook_events_created_at", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")
