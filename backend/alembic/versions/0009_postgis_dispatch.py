"""Add indexed spatial search and rider presence for dispatch.

Revision ID: 0009_postgis_dispatch
Revises: 0008_checkout_concurrency
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_postgis_dispatch"
down_revision = "0008_checkout_concurrency"
branch_labels = None
depends_on = None


STORE_POINT = "ST_SetSRID(ST_MakePoint(longitude::double precision, latitude::double precision), 4326)::geography"
VILLAGE_POINT = "ST_SetSRID(ST_MakePoint(longitude::double precision, latitude::double precision), 4326)::geography"
RIDER_POINT = "ST_SetSRID(ST_MakePoint(longitude::double precision, latitude::double precision), 4326)::geography"


def upgrade() -> None:
    op.create_table(
        "rider_presences",
        sa.Column("rider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_rider_presence_latitude"),
        sa.CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_rider_presence_longitude"),
    )
    op.create_index("ix_rider_presences_online_seen", "rider_presences", ["is_online", "last_seen_at"])

    op.execute(
        f"CREATE INDEX ix_stores_location_gist ON stores USING GIST (({STORE_POINT})) "
        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    op.execute(
        f"CREATE INDEX ix_villages_location_gist ON villages USING GIST (({VILLAGE_POINT})) "
        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    op.execute(f"CREATE INDEX ix_rider_presences_location_gist ON rider_presences USING GIST (({RIDER_POINT}))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rider_presences_location_gist")
    op.execute("DROP INDEX IF EXISTS ix_villages_location_gist")
    op.execute("DROP INDEX IF EXISTS ix_stores_location_gist")
    op.drop_index("ix_rider_presences_online_seen", table_name="rider_presences")
    op.drop_table("rider_presences")
