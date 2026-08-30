"""Add durable notification outbox retry and claim metadata.

Revision ID: 0012_notification_outbox
Revises: 0011_lifecycle_correlation
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_notification_outbox"
down_revision = "0011_lifecycle_correlation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notification_events", sa.Column("idempotency_key", sa.String(length=200), nullable=True))
    op.add_column("notification_events", sa.Column("request_id", sa.String(length=100), nullable=True))
    op.add_column("notification_events", sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("notification_events", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notification_events", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notification_events", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_notification_events_idempotency_key", "notification_events", ["idempotency_key"])
    op.create_index("ix_notification_events_request_id", "notification_events", ["request_id"])
    op.create_index("ix_notification_events_next_attempt_at", "notification_events", ["next_attempt_at"])
    op.create_index("ix_notification_events_locked_at", "notification_events", ["locked_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_events_locked_at", table_name="notification_events")
    op.drop_index("ix_notification_events_next_attempt_at", table_name="notification_events")
    op.drop_index("ix_notification_events_request_id", table_name="notification_events")
    op.drop_constraint("uq_notification_events_idempotency_key", "notification_events", type_="unique")
    op.drop_column("notification_events", "last_error")
    op.drop_column("notification_events", "locked_at")
    op.drop_column("notification_events", "next_attempt_at")
    op.drop_column("notification_events", "attempts")
    op.drop_column("notification_events", "request_id")
    op.drop_column("notification_events", "idempotency_key")
