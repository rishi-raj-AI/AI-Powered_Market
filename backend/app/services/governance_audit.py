"""Helpers for writing admin audit evidence in the business transaction."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.capabilities import Capability
from app.models.governance import AdministrativeAuditEvent
from app.models.user import User, UserRole


def request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "missing-request-id"))[:160]


def record_admin_action(
    db: Session,
    *,
    request: Request,
    actor: User,
    action: str,
    capability: Capability,
    resource_type: str,
    resource_id: object,
    previous_state: Mapping[str, Any] | None = None,
    resulting_state: Mapping[str, Any] | None = None,
    reason: str | None = None,
) -> AdministrativeAuditEvent:
    if actor.role != UserRole.ADMIN:
        raise ValueError("Administrative audit actors must be administrators")
    event = AdministrativeAuditEvent(
        actor_user_id=actor.id,
        action=action[:120],
        capability=capability.value,
        resource_type=resource_type[:80],
        resource_id=str(resource_id)[:120],
        previous_state=dict(previous_state or {}),
        resulting_state=dict(resulting_state or {}),
        reason=reason,
        request_id=request_id(request),
    )
    db.add(event)
    return event
