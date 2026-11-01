"""Durable webhook replay retry scheduling and starvation protection.

Revision ID: 0027_payment_webhook_retry_schedule
Revises: 0026_delivery_proof_limits
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_payment_webhook_retry_schedule"
down_revision = "0026_delivery_proof_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_webhook_events",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "payment_webhook_events",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_payment_webhook_events_next_attempt_at",
        "payment_webhook_events",
        ["next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_webhook_events_next_attempt_at",
        table_name="payment_webhook_events",
    )
    op.drop_column("payment_webhook_events", "next_attempt_at")
    op.drop_column("payment_webhook_events", "attempt_count")
