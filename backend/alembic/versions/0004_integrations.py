"""payment attempts, notification devices and notification outbox

Revision ID: 0004_integrations
Revises: 0003_orders_delivery
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_integrations"
down_revision = "0003_orders_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(512), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("app_version", sa.String(40)),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token", name="uq_device_registration_token"),
    )
    op.create_index("ix_device_registrations_user_id", "device_registrations", ["user_id"])

    op.create_table(
        "notification_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_notification_events_user_id", "notification_events", ["user_id"])
    op.create_index("ix_notification_events_event_type", "notification_events", ["event_type"])
    op.create_index("ix_notification_events_status", "notification_events", ["status"])

    op.create_table(
        "payment_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), server_default="razorpay", nullable=False),
        sa.Column("provider_order_id", sa.String(120), unique=True),
        sa.Column("provider_payment_id", sa.String(120), unique=True),
        sa.Column("status", sa.String(40), server_default="created", nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_attempts_order_id", "payment_attempts", ["order_id"])
    op.create_index("ix_payment_attempts_provider_order_id", "payment_attempts", ["provider_order_id"], unique=True)
    op.create_index("ix_payment_attempts_provider_payment_id", "payment_attempts", ["provider_payment_id"], unique=True)
    op.create_index("ix_payment_attempts_status", "payment_attempts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payment_attempts_status", table_name="payment_attempts")
    op.drop_index("ix_payment_attempts_provider_payment_id", table_name="payment_attempts")
    op.drop_index("ix_payment_attempts_provider_order_id", table_name="payment_attempts")
    op.drop_index("ix_payment_attempts_order_id", table_name="payment_attempts")
    op.drop_table("payment_attempts")

    op.drop_index("ix_notification_events_status", table_name="notification_events")
    op.drop_index("ix_notification_events_event_type", table_name="notification_events")
    op.drop_index("ix_notification_events_user_id", table_name="notification_events")
    op.drop_table("notification_events")

    op.drop_index("ix_device_registrations_user_id", table_name="device_registrations")
    op.drop_table("device_registrations")
