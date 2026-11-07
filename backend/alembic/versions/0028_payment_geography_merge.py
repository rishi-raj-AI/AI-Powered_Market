"""Merge payment webhook retry scheduling and confirmed address provenance.

Revision ID: 0028_payment_geography_merge
Revises: 0027_webhook_retry_schedule, 0027_address_location_provenance

An ancestry-only merge: both independent 0027 migrations remain unchanged.
No payment, address, service-area or territory data is rewritten.
"""
revision = "0028_payment_geography_merge"
down_revision = ("0027_webhook_retry_schedule", "0027_address_location_provenance")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Both parents perform their own additive DDL."""


def downgrade() -> None:
    """No DDL belongs to this merge revision."""
