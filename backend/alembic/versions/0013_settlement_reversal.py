"""Add settlement voiding and auditable reversal adjustments.

``ensure_settlement_entry`` was create-only, so an order that was paid and then
refunded left a live pending settlement and the merchant stayed queued to be
paid for money the customer got back.

Revision ID: 0013_settlement_reversal
Revises: 0012_payment_refunds
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_settlement_reversal"
down_revision: Union[str, None] = "0012_payment_refunds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "settlement_entries",
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "settlement_entries",
        sa.Column("void_reason", sa.String(length=80), nullable=True),
    )

    op.create_table(
        "settlement_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "settlement_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("settlement_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "merchant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("merchants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="owed"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_settlement_adjustment_idempotency_key"),
    )
    op.create_index(
        "ix_settlement_adjustments_settlement_entry_id",
        "settlement_adjustments",
        ["settlement_entry_id"],
    )
    op.create_index("ix_settlement_adjustments_order_id", "settlement_adjustments", ["order_id"])
    op.create_index("ix_settlement_adjustments_merchant_id", "settlement_adjustments", ["merchant_id"])
    op.create_index("ix_settlement_adjustments_status", "settlement_adjustments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_settlement_adjustments_status", table_name="settlement_adjustments")
    op.drop_index("ix_settlement_adjustments_merchant_id", table_name="settlement_adjustments")
    op.drop_index("ix_settlement_adjustments_order_id", table_name="settlement_adjustments")
    op.drop_index("ix_settlement_adjustments_settlement_entry_id", table_name="settlement_adjustments")
    op.drop_table("settlement_adjustments")
    op.drop_column("settlement_entries", "void_reason")
    op.drop_column("settlement_entries", "voided_at")
