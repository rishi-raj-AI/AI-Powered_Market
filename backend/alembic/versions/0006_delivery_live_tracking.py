"""Add delivery rider live-location history.

Revision ID: 0006_delivery_live_tracking
Revises: 0005_super_admin
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_delivery_live_tracking"
down_revision = "0005_super_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "delivery_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("deliveries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "delivery_partner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("heading_deg", sa.Float(), nullable=True),
        sa.Column("speed_mps", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_delivery_locations_delivery_id", "delivery_locations", ["delivery_id"])
    op.create_index("ix_delivery_locations_delivery_partner_id", "delivery_locations", ["delivery_partner_id"])
    op.create_index(
        "ix_delivery_locations_delivery_recorded",
        "delivery_locations",
        ["delivery_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_locations_delivery_recorded", table_name="delivery_locations")
    op.drop_index("ix_delivery_locations_delivery_partner_id", table_name="delivery_locations")
    op.drop_index("ix_delivery_locations_delivery_id", table_name="delivery_locations")
    op.drop_table("delivery_locations")
