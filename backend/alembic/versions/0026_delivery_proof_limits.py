"""Persist delivery proof abuse limits across requests and restarts.

Revision ID: 0026_delivery_proof_limits
Revises: 0025_support_ticket_idempotency
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_delivery_proof_limits"
down_revision = "0025_support_ticket_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_proofs", sa.Column("last_challenge_at", sa.DateTime(timezone=True)))
    op.add_column(
        "delivery_proofs",
        sa.Column("challenge_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "delivery_proofs",
        sa.Column("verification_attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("delivery_proofs", sa.Column("verification_locked_at", sa.DateTime(timezone=True)))
    # Preserve existing challenges and verified evidence. Historical attempt
    # counts are unknown; limits begin at rollout with one known issued code.
    op.execute(
        "UPDATE delivery_proofs SET challenge_count = 1, last_challenge_at = updated_at"
    )


def downgrade() -> None:
    op.drop_column("delivery_proofs", "verification_locked_at")
    op.drop_column("delivery_proofs", "verification_attempt_count")
    op.drop_column("delivery_proofs", "challenge_count")
    op.drop_column("delivery_proofs", "last_challenge_at")
