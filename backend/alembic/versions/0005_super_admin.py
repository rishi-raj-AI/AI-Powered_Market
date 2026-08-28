"""Persist the protected founding Super Admin capability.

Revision ID: 0005_super_admin
Revises: 0004_integrations
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_super_admin"
down_revision = "0004_integrations"
branch_labels = None
depends_on = None

FOUNDING_SUPER_ADMIN_PHONES = ("+917249723727", "7249723727")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_super_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    phones = ", ".join(f"'{phone}'" for phone in FOUNDING_SUPER_ADMIN_PHONES)
    op.execute(
        f"UPDATE users SET role = 'admin', is_super_admin = true, is_active = true, is_verified = true "
        f"WHERE phone IN ({phones})"
    )


def downgrade() -> None:
    op.drop_column("users", "is_super_admin")
