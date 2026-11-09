"""Add nullable address location provenance without rewriting legacy coordinates.

Revision ID: 0027_address_location_provenance
Revises: 0026_delivery_proof_limits

Historical addresses remain unchanged: NULL provenance does not prove
GPS/map confirmation, even when latitude and longitude already exist.
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_address_location_provenance"
down_revision = "0026_delivery_proof_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("addresses", sa.Column("location_source", sa.String(32), nullable=True))
    op.add_column(
        "addresses",
        sa.Column("location_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "addresses",
        sa.Column("location_accuracy_meters", sa.Float(), nullable=True),
    )
    op.add_column("addresses", sa.Column("place_id", sa.String(255), nullable=True))
    op.create_check_constraint(
        "ck_addresses_location_source",
        "addresses",
        "location_source IS NULL OR location_source IN ('gps', 'map_pin', 'searched_place')",
    )
    op.create_check_constraint(
        "ck_addresses_location_accuracy",
        "addresses",
        "location_accuracy_meters IS NULL OR location_accuracy_meters >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_addresses_location_accuracy", "addresses", type_="check")
    op.drop_constraint("ck_addresses_location_source", "addresses", type_="check")
    op.drop_column("addresses", "place_id")
    op.drop_column("addresses", "location_accuracy_meters")
    op.drop_column("addresses", "location_confirmed_at")
    op.drop_column("addresses", "location_source")
