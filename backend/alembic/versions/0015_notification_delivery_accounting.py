"""Add delivery accounting to the notification outbox.

Without an attempt count and a next-attempt time, a permanently failing event
is re-tried at the head of the queue on every flush and blocks everything
behind it.

Revision ID: 0015_notify_accounting
Revises: 0014_order_returned
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_notify_accounting"
down_revision: Union[str, None] = "0014_order_returned"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_events",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "notification_events",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_events",
        sa.Column("last_error", sa.String(length=300), nullable=True),
    )
    op.create_index(
        "ix_notification_events_next_attempt_at",
        "notification_events",
        ["next_attempt_at"],
    )
    # The worker scans this on every tick.
    op.create_index(
        "ix_notification_events_due",
        "notification_events",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_events_due", table_name="notification_events")
    op.drop_index("ix_notification_events_next_attempt_at", table_name="notification_events")
    op.drop_column("notification_events", "last_error")
    op.drop_column("notification_events", "next_attempt_at")
    op.drop_column("notification_events", "attempt_count")
