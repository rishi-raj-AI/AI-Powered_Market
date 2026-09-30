"""Add replay protection for support-ticket creation.

Revision ID: 0025_support_ticket_idempotency
Revises: 0024_external_identities
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0025_support_ticket_idempotency"
down_revision = "0024_external_identities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing tickets predate client-supplied replay keys, so retain NULL for
    # history while new clients can opt into user-scoped idempotency.
    op.add_column(
        "support_tickets",
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_support_tickets_user_idempotency",
        "support_tickets",
        ["user_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_support_tickets_user_idempotency", "support_tickets", type_="unique"
    )
    op.drop_column("support_tickets", "idempotency_key")
