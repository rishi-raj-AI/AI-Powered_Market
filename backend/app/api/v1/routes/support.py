from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.orders import Delivery, Order
from app.models.support import SupportTicket
from app.models.user import User, UserRole
from app.services.support_triage import triage_ticket

router = APIRouter(tags=["Support"])


class SupportTicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=5, max_length=5000)
    order_id: uuid.UUID | None = None
    delivery_id: uuid.UUID | None = None


class SupportTicketUpdate(BaseModel):
    status: Literal["open", "in_progress", "waiting_customer", "resolved", "closed"]
    resolution_notes: str | None = Field(default=None, max_length=1000)


def _ticket_payload(ticket: SupportTicket) -> dict:
    return {
        "id": str(ticket.id),
        "user_id": str(ticket.user_id),
        "order_id": str(ticket.order_id) if ticket.order_id else None,
        "delivery_id": str(ticket.delivery_id) if ticket.delivery_id else None,
        "subject": ticket.subject,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "triage_summary": ticket.triage_summary,
        "suggested_action": ticket.suggested_action,
        "resolution_notes": ticket.resolution_notes,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
    }


@router.post("/support/tickets", status_code=status.HTTP_201_CREATED)
def create_support_ticket(
    payload: SupportTicketCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    order = db.get(Order, payload.order_id) if payload.order_id else None
    if payload.order_id and order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order is not None and user.role != UserRole.ADMIN and order.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only reference your own order")

    delivery = db.get(Delivery, payload.delivery_id) if payload.delivery_id else None
    if payload.delivery_id and delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if delivery is not None:
        delivery_order = db.get(Order, delivery.order_id)
        if delivery_order is None:
            raise HTTPException(status_code=409, detail="Delivery order is missing")
        if user.role != UserRole.ADMIN and delivery_order.user_id != user.id:
            raise HTTPException(status_code=403, detail="You can only reference your own delivery")
        if order is not None and delivery.order_id != order.id:
            raise HTTPException(status_code=422, detail="Delivery does not belong to the referenced order")

    triage = triage_ticket(payload.subject, payload.description)
    ticket = SupportTicket(
        user_id=user.id,
        order_id=payload.order_id,
        delivery_id=payload.delivery_id,
        subject=payload.subject.strip(),
        description=payload.description.strip(),
        category=triage["category"],
        priority=triage["priority"],
        triage_summary=triage["summary"],
        suggested_action=triage["suggested_action"],
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return _ticket_payload(ticket)


@router.get("/support/tickets/me")
def my_support_tickets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    tickets = db.scalars(
        select(SupportTicket)
        .where(SupportTicket.user_id == user.id)
        .order_by(SupportTicket.created_at.desc())
        .limit(200)
    ).all()
    return [_ticket_payload(ticket) for ticket in tickets]


@router.get("/admin/support/tickets")
def admin_support_queue(
    ticket_status: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> list[dict]:
    stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(500)
    if ticket_status:
        stmt = stmt.where(SupportTicket.status == ticket_status)
    if priority:
        stmt = stmt.where(SupportTicket.priority == priority)
    return [_ticket_payload(ticket) for ticket in db.scalars(stmt).all()]


@router.patch("/admin/support/tickets/{ticket_id}")
def admin_update_support_ticket(
    ticket_id: uuid.UUID,
    payload: SupportTicketUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> dict:
    ticket = db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id).with_for_update())
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    ticket.status = payload.status
    ticket.resolution_notes = payload.resolution_notes
    if payload.status in {"resolved", "closed"}:
        ticket.resolved_at = ticket.resolved_at or datetime.now(timezone.utc)
    else:
        ticket.resolved_at = None
    db.commit()
    db.refresh(ticket)
    return _ticket_payload(ticket)
