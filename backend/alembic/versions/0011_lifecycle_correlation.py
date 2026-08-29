"""Correlate lifecycle audit events with HTTP requests and actors.

Revision ID: 0011_lifecycle_correlation
Revises: 0010_tracking_payments_settlement
"""

from alembic import op

revision = "0011_lifecycle_correlation"
down_revision = "0010_tracking_payments_settlement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION gaonone_audit_order_status() RETURNS trigger AS $$
    DECLARE
      request_id text := NULLIF(current_setting('gaonone.request_id', true), '');
      actor_id text := NULLIF(current_setting('gaonone.actor_user_id', true), '');
    BEGIN
      IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO status_transition_events (
          id, entity_type, entity_id, order_id, actor_user_id, from_status, to_status, event_metadata
        ) VALUES (
          gen_random_uuid(), 'order', NEW.id, NEW.id,
          CASE WHEN actor_id IS NULL THEN NULL ELSE actor_id::uuid END,
          OLD.status::text, NEW.status::text,
          CASE WHEN request_id IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('request_id', request_id) END
        );
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION gaonone_audit_delivery_status() RETURNS trigger AS $$
    DECLARE
      request_id text := NULLIF(current_setting('gaonone.request_id', true), '');
      actor_id text := NULLIF(current_setting('gaonone.actor_user_id', true), '');
    BEGIN
      IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO status_transition_events (
          id, entity_type, entity_id, order_id, delivery_id, actor_user_id,
          from_status, to_status, reason, event_metadata
        ) VALUES (
          gen_random_uuid(), 'delivery', NEW.id, NEW.order_id, NEW.id,
          CASE WHEN actor_id IS NULL THEN NULL ELSE actor_id::uuid END,
          OLD.status::text, NEW.status::text,
          CASE WHEN NEW.status::text = 'failed' THEN NEW.failure_reason ELSE NULL END,
          CASE WHEN request_id IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('request_id', request_id) END
        );
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
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
