"""Add delivery failure, proof-of-delivery and status audit support.

Revision ID: 0007_delivery_operations
Revises: 0006_delivery_live_tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_delivery_operations"
down_revision = "0006_delivery_live_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deliveries", sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deliveries", sa.Column("failure_reason", sa.String(length=80), nullable=True))
    op.add_column("deliveries", sa.Column("failure_notes", sa.String(length=500), nullable=True))
    op.add_column("deliveries", sa.Column("failure_evidence_url", sa.String(length=500), nullable=True))

    op.create_table(
        "delivery_proofs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("otp_hash", sa.String(length=64), nullable=False),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_url", sa.String(length=500), nullable=True),
        sa.Column("recipient_name", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_delivery_proofs_delivery_id", "delivery_proofs", ["delivery_id"], unique=True)

    op.create_table(
        "status_transition_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("delivery_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("from_status", sa.String(length=40), nullable=False),
        sa.Column("to_status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=160), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_status_transition_events_entity_type", "status_transition_events", ["entity_type"])
    op.create_index("ix_status_transition_events_entity_id", "status_transition_events", ["entity_id"])
    op.create_index("ix_status_transition_events_order_id", "status_transition_events", ["order_id"])
    op.create_index("ix_status_transition_events_delivery_id", "status_transition_events", ["delivery_id"])
    op.create_index("ix_status_transition_events_actor_user_id", "status_transition_events", ["actor_user_id"])
    op.create_index("ix_status_transition_events_created_at", "status_transition_events", ["created_at"])

    op.execute("""
    CREATE OR REPLACE FUNCTION gaonone_audit_order_status() RETURNS trigger AS $$
    BEGIN
      IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO status_transition_events (
          id, entity_type, entity_id, order_id, from_status, to_status, event_metadata
        ) VALUES (
          gen_random_uuid(), 'order', NEW.id, NEW.id, OLD.status::text, NEW.status::text, '{}'::jsonb
        );
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER trg_audit_order_status
    AFTER UPDATE OF status ON orders
    FOR EACH ROW EXECUTE FUNCTION gaonone_audit_order_status();
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION gaonone_audit_delivery_status() RETURNS trigger AS $$
    BEGIN
      IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO status_transition_events (
          id, entity_type, entity_id, order_id, delivery_id, from_status, to_status, reason, event_metadata
        ) VALUES (
          gen_random_uuid(), 'delivery', NEW.id, NEW.order_id, NEW.id, OLD.status::text, NEW.status::text,
          CASE WHEN NEW.status::text = 'failed' THEN NEW.failure_reason ELSE NULL END,
          '{}'::jsonb
        );
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute("""
    CREATE TRIGGER trg_audit_delivery_status
    AFTER UPDATE OF status ON deliveries
    FOR EACH ROW EXECUTE FUNCTION gaonone_audit_delivery_status();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_delivery_status ON deliveries")
    op.execute("DROP FUNCTION IF EXISTS gaonone_audit_delivery_status()")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_order_status ON orders")
    op.execute("DROP FUNCTION IF EXISTS gaonone_audit_order_status()")

    op.drop_index("ix_status_transition_events_created_at", table_name="status_transition_events")
    op.drop_index("ix_status_transition_events_actor_user_id", table_name="status_transition_events")
    op.drop_index("ix_status_transition_events_delivery_id", table_name="status_transition_events")
    op.drop_index("ix_status_transition_events_order_id", table_name="status_transition_events")
    op.drop_index("ix_status_transition_events_entity_id", table_name="status_transition_events")
    op.drop_index("ix_status_transition_events_entity_type", table_name="status_transition_events")
    op.drop_table("status_transition_events")

    op.drop_index("ix_delivery_proofs_delivery_id", table_name="delivery_proofs")
    op.drop_table("delivery_proofs")

    op.drop_column("deliveries", "failure_evidence_url")
    op.drop_column("deliveries", "failure_notes")
    op.drop_column("deliveries", "failure_reason")
    op.drop_column("deliveries", "failed_at")
