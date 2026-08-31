"""Archive addresses instead of deleting them, and snapshot the delivery address.

Deleting an address that any order referenced raised a foreign-key violation
and surfaced as an unhandled 500. Orders also pointed at the live address row,
so order history described wherever the address pointed today rather than where
the order actually went.

Revision ID: 0016_address_lifecycle
Revises: 0015_notify_accounting
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_address_lifecycle"
down_revision: Union[str, None] = "0015_notify_accounting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "addresses",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_addresses_archived_at", "addresses", ["archived_at"])
    op.add_column(
        "orders",
        sa.Column(
            "delivery_address",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    # Backfill from the currently referenced address so existing orders carry
    # their delivery detail. This is the closest truth available and is strictly
    # better than an empty snapshot.
    op.execute(
        """
        UPDATE orders o
        SET delivery_address = jsonb_strip_nulls(
            jsonb_build_object(
                'recipient_name', a.recipient_name,
                'phone', a.phone,
                'house_details', a.house_details,
                'landmark', a.landmark,
                'directions', a.directions,
                'latitude', a.latitude,
                'longitude', a.longitude,
                'village_id', a.village_id::text,
                'backfilled', true
            )
        )
        FROM addresses a
        WHERE a.id = o.address_id
        """
    )


def downgrade() -> None:
    op.drop_column("orders", "delivery_address")
    op.drop_index("ix_addresses_archived_at", table_name="addresses")
    op.drop_column("addresses", "archived_at")
