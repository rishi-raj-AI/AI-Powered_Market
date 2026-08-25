"""marketplace foundation

Revision ID: 0002_marketplace_foundation
Revises: 0001_create_users
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_marketplace_foundation"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    merchant_status = postgresql.ENUM("pending", "approved", "suspended", name="merchant_status", create_type=False)
    merchant_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "villages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("taluka", sa.String(120)),
        sa.Column("district", sa.String(120), nullable=False),
        sa.Column("state", sa.String(120), nullable=False),
        sa.Column("pincode", sa.String(10)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "district", "state", name="uq_village_location"),
    )
    op.create_index("ix_villages_name", "villages", ["name"])
    op.create_index("ix_villages_district", "villages", ["district"])
    op.create_index("ix_villages_state", "villages", ["state"])
    op.create_index("ix_villages_pincode", "villages", ["pincode"])

    op.create_table(
        "service_areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("hub_village_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("villages.id"), nullable=False),
        sa.Column("radius_km", sa.Float(), server_default="10", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("village_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("villages.id"), nullable=False),
        sa.Column("label", sa.String(40), server_default="Home", nullable=False),
        sa.Column("recipient_name", sa.String(120)),
        sa.Column("phone", sa.String(20)),
        sa.Column("house_details", sa.String(200)),
        sa.Column("landmark", sa.String(240), nullable=False),
        sa.Column("directions", sa.Text()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_addresses_user_id", "addresses", ["user_id"])
    op.create_index("ix_addresses_village_id", "addresses", ["village_id"])

    op.create_table(
        "merchants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("business_name", sa.String(160), nullable=False),
        sa.Column("status", merchant_status, server_default="pending", nullable=False),
        sa.Column("gstin", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_merchants_owner_user_id", "merchants", ["owner_user_id"], unique=True)

    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("village_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("villages.id"), nullable=False),
        sa.Column("service_area_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service_areas.id")),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("phone", sa.String(20)),
        sa.Column("landmark", sa.String(240)),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("opens_at", sa.Time()),
        sa.Column("closes_at", sa.Time()),
        sa.Column("delivery_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("pickup_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_stores_merchant_id", "stores", ["merchant_id"])
    op.create_index("ix_stores_village_id", "stores", ["village_id"])
    op.create_index("ix_stores_service_area_id", "stores", ["service_area_id"])
    op.create_index("ix_stores_name", "stores", ["name"])
    op.create_index("ix_stores_slug", "stores", ["slug"], unique=True)

    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("brand", sa.String(120)),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("image_url", sa.String(500)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_brand", "products", ["brand"])

    op.create_table(
        "store_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("mrp", sa.Numeric(10, 2)),
        sa.Column("stock_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_available", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("store_id", "product_id", name="uq_store_product"),
    )
    op.create_index("ix_store_products_store_id", "store_products", ["store_id"])
    op.create_index("ix_store_products_product_id", "store_products", ["product_id"])


def downgrade() -> None:
    op.drop_table("store_products")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("stores")
    op.drop_table("merchants")
    op.drop_table("addresses")
    op.drop_table("service_areas")
    op.drop_table("villages")
    postgresql.ENUM(name="merchant_status").drop(op.get_bind(), checkfirst=True)
