"""Add checkout idempotency and stock restoration metadata.

Revision ID: 0008_checkout_concurrency
Revises: 0007_delivery_operations
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_checkout_concurrency"
down_revision = "0007_delivery_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("orders", sa.Column("stock_restored_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_orders_user_idempotency_key",
        "orders",
        ["user_id", "idempotency_key"],
    )
    op.create_index("ix_orders_idempotency_key", "orders", ["idempotency_key"])


def downgrade() -> None:
    op.drop_index("ix_orders_idempotency_key", table_name="orders")
    op.drop_constraint("uq_orders_user_idempotency_key", "orders", type_="unique")
    op.drop_column("orders", "stock_restored_at")
    op.drop_column("orders", "idempotency_key")
