"""Join additive territory foundation with the payment/geography migration bridge.

Revision ID: 0029_payment_geo_territory_merge
Revises: 0028_payment_geography_merge, 0028_delivery_territories

This ancestry-only merge preserves both historical migration paths.
No payment, address, store, service-area or territory data is changed here.
The territory foundation migration only creates draft-only tables.
"""

revision = "0029_payment_geo_territory_merge"
down_revision = ("0028_payment_geography_merge", "0028_delivery_territories")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Both parents perform their own additive DDL."""


def downgrade() -> None:
    """No DDL belongs to this merge revision."""
