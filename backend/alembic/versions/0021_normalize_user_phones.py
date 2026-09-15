"""Canonicalize Indian mobile identities without merging accounts.

Revision ID: 0021_normalize_user_phones
Revises: 0020_unified_support_workflow
"""

from typing import Sequence, Union
import re

import sqlalchemy as sa
from alembic import op

revision: str = "0021_normalize_user_phones"
down_revision: Union[str, None] = "0020_unified_support_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_phone(value: str) -> str:
    # Frozen migration logic: future application validation changes must not
    # alter how an already-released migration behaves.
    digits = re.sub(r"[\s()\-]", "", value.strip())
    if digits.startswith("+"):
        digits = digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise ValueError
    return f"+91{digits}"


def _phone_updates(rows) -> list[tuple[object, str]]:
    normalized: dict[str, list[object]] = {}
    updates: list[tuple[object, str]] = []
    for row in rows:
        try:
            phone = _normalize_phone(row["phone"])
        except ValueError as exc:
            raise RuntimeError("A user has a non-canonicalizable phone; resolve it before migration") from exc
        normalized.setdefault(phone, []).append(row["id"])
        updates.append((row["id"], phone))
    if any(len(user_ids) > 1 for user_ids in normalized.values()):
        raise RuntimeError("Phone normalization would collide accounts; resolve duplicates without merging before migration")
    return updates


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, phone FROM users")).mappings().all()
    updates = _phone_updates(rows)
    for user_id, phone in updates:
        connection.execute(sa.text("UPDATE users SET phone=:phone WHERE id=:id"), {"phone": phone, "id": user_id})


def downgrade() -> None:
    # Canonical formatting is intentionally retained; the prior representation
    # cannot be reconstructed safely.
    pass
