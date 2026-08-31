"""Add durable refund obligations and a pending-refund payment state.

Refunds were previously asserted by writing ``payment_status = refunded``
without any provider call. This adds the record that makes a refund an
obligation the system can execute, retry and audit.

Revision ID: 0012_payment_refunds
Revises: 0011_cod_collection
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_payment_refunds"
down_revision: Union[str, None] = "0011_cod_collection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New enum values cannot be used in the transaction that adds them, so this
    # runs outside the migration transaction.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'refund_pending'")

    op.create_table(
        "payment_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payment_attempts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="razorpay"),
        sa.Column("provider_payment_id", sa.String(length=120), nullable=True),
        sa.Column("provider_refund_id", sa.String(length=120), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="requested"),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("provider_status", sa.String(length=40), nullable=True),
        sa.Column("failure_reason", sa.String(length=300), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_refund_idempotency_key"),
        sa.UniqueConstraint("provider_refund_id", name="uq_payment_refund_provider_refund_id"),
    )
    op.create_index("ix_payment_refunds_order_id", "payment_refunds", ["order_id"])
    op.create_index("ix_payment_refunds_payment_attempt_id", "payment_refunds", ["payment_attempt_id"])
    op.create_index("ix_payment_refunds_provider_payment_id", "payment_refunds", ["provider_payment_id"])
    op.create_index("ix_payment_refunds_provider_refund_id", "payment_refunds", ["provider_refund_id"])
    op.create_index("ix_payment_refunds_status", "payment_refunds", ["status"])
    # The worker scans for owed refunds by status and age on every tick.
    op.create_index(
        "ix_payment_refunds_due",
        "payment_refunds",
        ["status", "attempt_count", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_refunds_due", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_status", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_provider_refund_id", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_provider_payment_id", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_payment_attempt_id", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_order_id", table_name="payment_refunds")
    op.drop_table("payment_refunds")
    # Enum values are not removed: dropping a value that rows may reference is
    # destructive, and the forward-only contract makes it unnecessary.
