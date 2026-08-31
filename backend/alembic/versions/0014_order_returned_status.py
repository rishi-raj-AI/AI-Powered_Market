"""Add the returned order status.

A delivery that failed after pickup had no exit: out_for_delivery only
transitioned to delivered, and recovery refused anything already picked up, so
the order was stranded and any prepaid money with it.

Revision ID: 0014_order_returned
Revises: 0013_settlement_reversal
Create Date: 2026-08-30
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0014_order_returned"
down_revision: Union[str, None] = "0013_settlement_reversal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'returned'")


def downgrade() -> None:
    # Enum values are not removed: dropping a value rows may reference is
    # destructive and the migration contract is forward-only.
    pass
