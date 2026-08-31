"""Allow a service area to set its own delivery fee.

The fee was a literal in the checkout code, so changing it meant a deploy and
every area paid the same regardless of distance or economics.

Revision ID: 0017_area_delivery_fee
Revises: 0016_address_lifecycle
Create Date: 2026-08-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_area_delivery_fee"
down_revision: Union[str, None] = "0016_address_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable on purpose: null means "use the configured platform default", so
    # existing areas keep today's pricing and a new area needs no decision.
    op.add_column(
        "service_areas",
        sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("service_areas", "delivery_fee")
