"""Add explicit cash-on-delivery collection records.

Revision ID: 0011_cod_collection
Revises: 0010_payments_settlement
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0011_cod_collection"
down_revision: Union[str, None] = "0010_payments_settlement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cod_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("collected_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["delivery_id"], ["deliveries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["collected_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id", name="uq_cod_collections_delivery_id"),
        sa.UniqueConstraint("order_id", name="uq_cod_collections_order_id"),
    )
    op.create_index("ix_cod_collections_delivery_id", "cod_collections", ["delivery_id"])
    op.create_index("ix_cod_collections_order_id", "cod_collections", ["order_id"])
    op.create_index("ix_cod_collections_collected_by_user_id", "cod_collections", ["collected_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_cod_collections_collected_by_user_id", table_name="cod_collections")
    op.drop_index("ix_cod_collections_order_id", table_name="cod_collections")
    op.drop_index("ix_cod_collections_delivery_id", table_name="cod_collections")
    op.drop_table("cod_collections")
