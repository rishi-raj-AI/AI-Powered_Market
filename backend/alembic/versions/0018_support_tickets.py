"""Add durable support tickets.

Revision ID: 0018_support_tickets
Revises: 0017_area_delivery_fee
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_support_tickets"
down_revision = "0017_area_delivery_fee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL")),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="SET NULL")),
        sa.Column("subject", sa.String(180), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(40), nullable=False), sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("triage_summary", sa.String(500), nullable=False), sa.Column("suggested_action", sa.String(500), nullable=False),
        sa.Column("resolution_notes", sa.String(1000)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    for column in ("user_id", "order_id", "delivery_id", "category", "priority", "status", "created_at"):
        op.create_index(f"ix_support_tickets_{column}", "support_tickets", [column])


def downgrade() -> None:
    op.drop_table("support_tickets")
