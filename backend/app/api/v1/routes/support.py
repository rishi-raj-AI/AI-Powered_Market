import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.orders import Delivery, Order
from app.models.support import SupportTicket
from app.models.user import User, UserRole
from app.services.support_triage import triage_ticket

router = APIRouter(tags=["Support"])


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=5, max_length=5000)
    order_id: uuid.UUID | None = None
    delivery_id: uuid.UUID | None = None


class TicketUpdate(BaseModel):
    status: Literal["open", "in_progress", "waiting_customer", "resolved", "closed"]
    resolution_notes: str | None = Field(default=None, max_length=1000)


def _read(ticket: SupportTicket) -> dict:
    return {name: getattr(ticket, name) for name in ("id", "user_id", "order_id", "delivery_id", "subject", "description", "category", "priority", "status", "triage_summary", "suggested_action", "resolution_notes", "created_at", "updated_at", "resolved_at")}


def _validate_references(db: Session, payload: TicketCreate, user: User) -> None:
    order = db.get(Order, payload.order_id) if payload.order_id else None
    if payload.order_id and order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order is not None and user.role != UserRole.ADMIN and order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    delivery = db.get(Delivery, payload.delivery_id) if payload.delivery_id else None
    if payload.delivery_id and delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if delivery is not None:
        delivery_order = db.get(Order, delivery.order_id)
        if delivery_order is None or (user.role != UserRole.ADMIN and delivery_order.user_id != user.id):
            raise HTTPException(status_code=404, detail="Delivery not found")
        if order is not None and delivery.order_id != order.id:
            raise HTTPException(status_code=422, detail="Delivery does not belong to the referenced order")


@router.post("/support/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _validate_references(db, payload, user)
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
    db.add(ticket); db.commit(); db.refresh(ticket)
    return _read(ticket)


@router.get("/support/tickets/me")
def my_tickets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(SupportTicket).where(SupportTicket.user_id == user.id).order_by(SupportTicket.created_at.desc()).limit(200)).all()
    return [_read(row) for row in rows]


@router.get("/admin/support/tickets")
def admin_queue(db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    return [_read(row) for row in db.scalars(select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(500)).all()]


@router.patch("/admin/support/tickets/{ticket_id}")
def update_ticket(ticket_id: uuid.UUID, payload: TicketUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.ADMIN))):
    ticket = db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id).with_for_update())
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    ticket.status = payload.status; ticket.resolution_notes = payload.resolution_notes
    ticket.resolved_at = (
        ticket.resolved_at or datetime.now(timezone.utc)
        if payload.status in {"resolved", "closed"}
        else None
    )
    db.commit(); db.refresh(ticket)
    return _read(ticket)
