"""Add attributable administrative audit events.

Revision ID: 0019_administrative_audit
Revises: 0018_support_tickets
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_administrative_audit"
down_revision = "0018_support_tickets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "administrative_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(120), nullable=False),
        sa.Column("previous_state", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resulting_state", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reason", sa.Text()),
        sa.Column("request_id", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in (
        "actor_user_id",
        "action",
        "capability",
        "resource_type",
        "resource_id",
        "request_id",
        "created_at",
    ):
        op.create_index(
            f"ix_administrative_audit_events_{column}",
            "administrative_audit_events",
            [column],
        )
    # This protects application DML. As with any owner-managed PostgreSQL
    # trigger, a database owner can still alter/drop the trigger or truncate
    # the table; database-owner access therefore remains a separate control.
    op.execute(
        """
        CREATE FUNCTION prevent_administrative_audit_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'administrative audit events are append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER administrative_audit_events_append_only
        BEFORE UPDATE OR DELETE ON administrative_audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_administrative_audit_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS administrative_audit_events_append_only "
        "ON administrative_audit_events"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_administrative_audit_mutation()")
    op.drop_table("administrative_audit_events")
