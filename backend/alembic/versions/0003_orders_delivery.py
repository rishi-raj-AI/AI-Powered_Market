"""orders and delivery

Revision ID: 0003_orders_delivery
Revises: 0002_marketplace_foundation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_orders_delivery"
down_revision = "0002_marketplace_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    order_status = postgresql.ENUM("placed", "accepted", "preparing", "ready", "out_for_delivery", "delivered", "cancelled", name="order_status", create_type=False)
    payment_method = postgresql.ENUM("cod", "upi", name="payment_method", create_type=False)
    payment_status = postgresql.ENUM("pending", "paid", "failed", "refunded", name="payment_status", create_type=False)
    delivery_status = postgresql.ENUM("unassigned", "assigned", "picked_up", "delivered", "failed", name="delivery_status", create_type=False)
    for enum_type in (order_status, payment_method, payment_status, delivery_status):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "carts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_carts_user_id", "carts", ["user_id"], unique=True)
    op.create_index("ix_carts_store_id", "carts", ["store_id"])

    op.create_table(
        "cart_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("store_product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("store_products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.UniqueConstraint("cart_id", "store_product_id", name="uq_cart_store_product"),
    )
    op.create_index("ix_cart_items_cart_id", "cart_items", ["cart_id"])
    op.create_index("ix_cart_items_store_product_id", "cart_items", ["store_product_id"])

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_number", sa.String(32), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("address_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("addresses.id"), nullable=False),
        sa.Column("status", order_status, server_default="placed", nullable=False),
        sa.Column("payment_method", payment_method, nullable=False),
        sa.Column("payment_status", payment_status, server_default="pending", nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_store_id", "orders", ["store_id"])

    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name", sa.String(180), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    op.create_table(
        "deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("delivery_partner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("status", delivery_status, server_default="unassigned", nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("picked_up_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_deliveries_order_id", "deliveries", ["order_id"], unique=True)
    op.create_index("ix_deliveries_delivery_partner_id", "deliveries", ["delivery_partner_id"])


def downgrade() -> None:
    op.drop_table("deliveries")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("cart_items")
    op.drop_table("carts")
    for name in ("delivery_status", "payment_status", "payment_method", "order_status"):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
