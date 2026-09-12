"""Extend support tickets with ownership, messaging and assignment.

Revision ID: 0020_unified_support_workflow
Revises: 0019_administrative_audit
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020_unified_support_workflow"
down_revision = "0019_administrative_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("support_tickets", sa.Column("store_id", postgresql.UUID(as_uuid=True)))
    op.add_column("support_tickets", sa.Column("requester_type", sa.String(20)))
    op.add_column("support_tickets", sa.Column("assigned_admin_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "support_tickets",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_support_tickets_store_id", "support_tickets", "stores", ["store_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_support_tickets_assigned_admin_id", "support_tickets", "users",
        ["assigned_admin_id"], ["id"], ondelete="SET NULL"
    )
    for column in ("store_id", "requester_type", "assigned_admin_id"):
        op.create_index(f"ix_support_tickets_{column}", "support_tickets", [column])

    # Existing tickets predate trustworthy requester-role snapshots. Preserve
    # that uncertainty as NULL rather than fabricating historical actor type.
    op.create_table(
        "support_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ticket_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "author_user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("author_type", sa.String(20), nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "visibility IN ('public', 'internal')",
            name="ck_support_messages_visibility",
        ),
        sa.UniqueConstraint(
            "ticket_id", "idempotency_key", name="uq_support_messages_ticket_idempotency"
        ),
    )
    for column in ("ticket_id", "author_user_id", "visibility", "created_at"):
        op.create_index(f"ix_support_messages_{column}", "support_messages", [column])


def downgrade() -> None:
    op.drop_table("support_messages")
    for column in ("assigned_admin_id", "requester_type", "store_id"):
        op.drop_index(f"ix_support_tickets_{column}", table_name="support_tickets")
    op.drop_constraint("fk_support_tickets_assigned_admin_id", "support_tickets", type_="foreignkey")
    op.drop_constraint("fk_support_tickets_store_id", "support_tickets", type_="foreignkey")
    for column in ("version", "assigned_admin_id", "requester_type", "store_id"):
        op.drop_column("support_tickets", column)
