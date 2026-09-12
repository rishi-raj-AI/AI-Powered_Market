import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ensure_capability, get_current_user, get_db, require_capability
from app.core.capabilities import Capability, has_capability
from app.models.commerce import Merchant, Store
from app.models.orders import Delivery, Order
from app.models.support import SupportMessage, SupportTicket
from app.models.user import User, UserRole
from app.services.governance_audit import record_admin_action
from app.services.notifications import enqueue_notification
from app.services.support_triage import triage_ticket

router = APIRouter(tags=["Support"])
TicketStatus = Literal["open", "in_progress", "waiting_customer", "resolved", "closed"]

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"in_progress", "waiting_customer", "resolved", "closed"}),
    "in_progress": frozenset({"waiting_customer", "resolved", "closed"}),
    "waiting_customer": frozenset({"in_progress", "resolved", "closed"}),
    "resolved": frozenset({"in_progress", "closed"}),
    "closed": frozenset({"open"}),
}


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=5, max_length=5000)
    store_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    delivery_id: uuid.UUID | None = None


class TicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: TicketStatus
    resolution_notes: str | None = Field(default=None, max_length=1000)
    expected_version: int | None = Field(default=None, ge=0)


class TicketAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_admin_id: uuid.UUID | None
    expected_version: int = Field(ge=0)


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=5000)
    idempotency_key: uuid.UUID

    @field_validator("body")
    @classmethod
    def body_must_have_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message body cannot be empty")
        return stripped


def _messages(
    db: Session,
    ticket_id: uuid.UUID,
    visibility: str,
    *,
    limit: int,
    offset: int,
) -> list[SupportMessage]:
    return list(
        db.scalars(
            select(SupportMessage)
            .where(
                SupportMessage.ticket_id == ticket_id,
                SupportMessage.visibility == visibility,
            )
            .order_by(SupportMessage.created_at, SupportMessage.id)
            .offset(offset)
            .limit(limit)
        ).all()
    )


def _public_message(message: SupportMessage) -> dict:
    return {
        "id": message.id,
        "author_type": message.author_type,
        "body": message.body,
        "created_at": message.created_at,
    }


def _internal_message(message: SupportMessage) -> dict:
    return _public_message(message) | {"author_user_id": message.author_user_id}


def _public_read(ticket: SupportTicket) -> dict:
    # Preserve legacy description/resolution_notes as public content. Staff-only
    # triage and internal messages are exposed only by admin serializers.
    return {
        name: getattr(ticket, name)
        for name in (
            "id", "user_id", "store_id", "order_id", "delivery_id",
            "requester_type", "subject", "description", "category", "priority",
            "status", "resolution_notes", "version", "created_at", "updated_at",
            "resolved_at",
        )
    }


def _admin_read(ticket: SupportTicket) -> dict:
    return _public_read(ticket) | {
        "assigned_admin_id": ticket.assigned_admin_id,
        "triage_summary": ticket.triage_summary,
        "suggested_action": ticket.suggested_action,
    }


def _validate_references(
    db: Session, payload: TicketCreate, user: User
) -> tuple[Order | None, Delivery | None, Store | None]:
    explicit_order = db.get(Order, payload.order_id) if payload.order_id else None
    if payload.order_id and explicit_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    explicit_delivery = db.get(Delivery, payload.delivery_id) if payload.delivery_id else None
    if payload.delivery_id and explicit_delivery is None:
        raise HTTPException(status_code=404, detail="Delivery not found")
    delivery_order = None
    if explicit_delivery is not None:
        delivery_order = db.get(Order, explicit_delivery.order_id)
        if delivery_order is None:
            raise HTTPException(status_code=404, detail="Delivery not found")
    explicit_store = db.get(Store, payload.store_id) if payload.store_id else None
    if payload.store_id and explicit_store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    has_reference = any((payload.store_id, payload.order_id, payload.delivery_id))
    if user.role == UserRole.ADMIN:
        ensure_capability(user, Capability.SUPPORT_MANAGE)
    elif user.role == UserRole.CUSTOMER:
        authorized_orders = tuple(
            order for order in (explicit_order, delivery_order) if order is not None
        )
        if has_reference and (
            not authorized_orders
            or any(order.user_id != user.id for order in authorized_orders)
            or (
                explicit_order is not None
                and delivery_order is not None
                and explicit_order.id != delivery_order.id
            )
            or (
                explicit_store is not None
                and any(order.store_id != explicit_store.id for order in authorized_orders)
            )
        ):
            raise HTTPException(status_code=404, detail="Linked support context not found")
    elif user.role == UserRole.MERCHANT:
        merchant = db.scalar(select(Merchant).where(Merchant.owner_user_id == user.id))
        referenced_stores = tuple(
            store
            for store in (
                explicit_store,
                db.get(Store, explicit_order.store_id) if explicit_order else None,
                db.get(Store, delivery_order.store_id) if delivery_order else None,
            )
            if store is not None
        )
        if has_reference and (
            merchant is None
            or not referenced_stores
            or any(store.merchant_id != merchant.id for store in referenced_stores)
        ):
            raise HTTPException(status_code=404, detail="Linked support context not found")
    elif user.role == UserRole.DELIVERY:
        if has_reference and (
            explicit_delivery is None
            or explicit_delivery.delivery_partner_id != user.id
            or (
                explicit_order is not None
                and delivery_order is not None
                and explicit_order.id != delivery_order.id
            )
            or (
                explicit_store is not None
                and delivery_order is not None
                and explicit_store.id != delivery_order.store_id
            )
        ):
            raise HTTPException(status_code=404, detail="Linked support context not found")
    else:
        raise HTTPException(status_code=403, detail="Unsupported requester role")

    # Relationship errors are safe to reveal only after every explicitly supplied
    # resource has been proven to belong to the requester context.
    if (
        explicit_order is not None
        and delivery_order is not None
        and explicit_order.id != delivery_order.id
    ):
        raise HTTPException(
            status_code=422, detail="Delivery does not belong to the referenced order"
        )
    order = explicit_order or delivery_order
    if (
        explicit_store is not None
        and order is not None
        and order.store_id != explicit_store.id
    ):
        raise HTTPException(
            status_code=422, detail="Order does not belong to the referenced store"
        )
    store = explicit_store or (db.get(Store, order.store_id) if order else None)
    if order is not None and store is None:
        raise HTTPException(status_code=404, detail="Linked support context not found")
    return order, explicit_delivery, store


def _owned_ticket(db: Session, ticket_id: uuid.UUID, user: User) -> SupportTicket:
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None or ticket.user_id != user.id:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    return ticket


def _locked_ticket(db: Session, ticket_id: uuid.UUID) -> SupportTicket:
    ticket = db.scalar(
        select(SupportTicket).where(SupportTicket.id == ticket_id).with_for_update()
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    return ticket


def _check_version(ticket: SupportTicket, expected_version: int | None) -> None:
    if expected_version is not None and ticket.version != expected_version:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Support ticket changed; refresh and retry",
                "version": ticket.version,
            },
        )


def _add_message(
    db: Session,
    *,
    ticket: SupportTicket,
    author: User,
    visibility: str,
    payload: MessageCreate,
) -> tuple[SupportMessage, bool]:
    existing = db.scalar(
        select(SupportMessage).where(
            SupportMessage.ticket_id == ticket.id,
            SupportMessage.idempotency_key == payload.idempotency_key,
        )
    )
    body = payload.body.strip()
    if existing is not None:
        if (
            existing.author_user_id != author.id
            or existing.visibility != visibility
            or existing.body != body
        ):
            raise HTTPException(status_code=409, detail="Idempotency key payload mismatch")
        return existing, False
    message = SupportMessage(
        ticket_id=ticket.id,
        author_user_id=author.id,
        author_type=author.role.value,
        visibility=visibility,
        idempotency_key=payload.idempotency_key,
        body=body,
    )
    ticket.version += 1
    db.add(message)
    db.flush()
    return message, True


@router.post("/support/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order, delivery, store = _validate_references(db, payload, user)
    triage = triage_ticket(payload.subject, payload.description)
    ticket = SupportTicket(
        user_id=user.id,
        store_id=store.id if store else None,
        order_id=order.id if order else None,
        delivery_id=delivery.id if delivery else None,
        requester_type=user.role.value,
        subject=payload.subject.strip(),
        description=payload.description.strip(),
        category=triage["category"],
        priority=triage["priority"],
        triage_summary=triage["summary"],
        suggested_action=triage["suggested_action"],
    )
    db.add(ticket)
    db.flush()
    if user.role == UserRole.ADMIN:
        record_admin_action(
            db, request=request, actor=user, action="support.ticket_created",
            capability=Capability.SUPPORT_MANAGE, resource_type="support_ticket",
            resource_id=ticket.id, resulting_state={"status": ticket.status},
            reason="administrator_support_escalation",
        )
    db.commit()
    db.refresh(ticket)
    return _public_read(ticket)


@router.get("/support/tickets/me")
def my_tickets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(SupportTicket)
        .where(SupportTicket.user_id == user.id)
        .order_by(SupportTicket.created_at.desc())
        .limit(200)
    ).all()
    return [_public_read(row) for row in rows]


@router.get("/support/tickets/{ticket_id}")
def my_ticket(
    ticket_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _public_read(_owned_ticket(db, ticket_id, user))


@router.get("/support/tickets/{ticket_id}/messages")
def my_ticket_messages(
    ticket_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _owned_ticket(db, ticket_id, user)
    return [
        _public_message(message)
        for message in _messages(
            db, ticket.id, "public", limit=limit, offset=offset
        )
    ]


@router.post("/support/tickets/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
def add_requester_message(
    ticket_id: uuid.UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _locked_ticket(db, ticket_id)
    if ticket.user_id != user.id:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    if ticket.status == "closed":
        raise HTTPException(status_code=409, detail="Closed tickets must be reopened before replying")
    message, created = _add_message(
        db, ticket=ticket, author=user, visibility="public", payload=payload
    )
    if not created:
        return _public_message(message)
    if ticket.status == "waiting_customer":
        ticket.status = "in_progress"
    if ticket.assigned_admin_id:
        enqueue_notification(
            db, user_id=ticket.assigned_admin_id,
            event_type="support.requester_replied", title="Requester replied",
            body="A requester replied to an assigned support ticket.",
            data={"ticket_id": str(ticket.id)},
        )
    db.commit()
    db.refresh(message)
    return _public_message(message)


@router.get("/admin/support/tickets")
def admin_queue(
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.SUPPORT_MANAGE)),
):
    rows = db.scalars(
        select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(500)
    ).all()
    return [_admin_read(row) for row in rows]


@router.get("/admin/support/tickets/{ticket_id}")
def admin_ticket(
    ticket_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.SUPPORT_MANAGE)),
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    return _admin_read(ticket)


@router.get("/admin/support/tickets/{ticket_id}/messages")
def admin_ticket_messages(
    ticket_id: uuid.UUID,
    visibility: Literal["public", "internal"] = Query(default="public"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_capability(Capability.SUPPORT_MANAGE)),
):
    ticket = db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    serializer = _internal_message if visibility == "internal" else _public_message
    return [
        serializer(message)
        for message in _messages(
            db, ticket.id, visibility, limit=limit, offset=offset
        )
    ]


@router.patch("/admin/support/tickets/{ticket_id}")
def update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.SUPPORT_MANAGE)),
):
    ticket = _locked_ticket(db, ticket_id)
    _check_version(ticket, payload.expected_version)
    notes_supplied = "resolution_notes" in payload.model_fields_set
    next_notes = payload.resolution_notes if notes_supplied else ticket.resolution_notes
    if payload.status == ticket.status and next_notes == ticket.resolution_notes:
        return _admin_read(ticket)
    if payload.status != ticket.status and payload.status not in ALLOWED_TRANSITIONS[ticket.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid support transition from {ticket.status} to {payload.status}",
        )
    previous = {
        "status": ticket.status,
        "has_resolution_notes": bool(ticket.resolution_notes),
        "version": ticket.version,
    }
    ticket.status = payload.status
    if notes_supplied:
        ticket.resolution_notes = payload.resolution_notes
    ticket.resolved_at = (
        ticket.resolved_at or datetime.now(timezone.utc)
        if payload.status in {"resolved", "closed"}
        else None
    )
    ticket.version += 1
    record_admin_action(
        db, request=request, actor=admin, action="support.ticket_updated",
        capability=Capability.SUPPORT_MANAGE, resource_type="support_ticket",
        resource_id=ticket.id, previous_state=previous,
        resulting_state={
            "status": ticket.status,
            "has_resolution_notes": bool(ticket.resolution_notes),
            "version": ticket.version,
        },
        reason="support_ticket_resolution",
    )
    enqueue_notification(
        db, user_id=ticket.user_id, event_type="support.ticket_updated",
        title="Support ticket updated",
        body=f"Your support ticket is now {ticket.status.replace('_', ' ')}.",
        data={"ticket_id": str(ticket.id), "status": ticket.status},
    )
    db.commit()
    db.refresh(ticket)
    return _admin_read(ticket)


@router.patch("/admin/support/tickets/{ticket_id}/assignment")
def assign_ticket(
    ticket_id: uuid.UUID,
    payload: TicketAssignment,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.SUPPORT_MANAGE)),
):
    ticket = _locked_ticket(db, ticket_id)
    _check_version(ticket, payload.expected_version)
    assignee = db.get(User, payload.assigned_admin_id) if payload.assigned_admin_id else None
    if payload.assigned_admin_id and (
        assignee is None
        or not has_capability(assignee, Capability.SUPPORT_MANAGE)
        or not assignee.is_active
        or not assignee.is_verified
    ):
        raise HTTPException(status_code=422, detail="Select an active verified administrator")
    if ticket.assigned_admin_id == payload.assigned_admin_id:
        return _admin_read(ticket)
    previous_id = ticket.assigned_admin_id
    ticket.assigned_admin_id = payload.assigned_admin_id
    ticket.version += 1
    record_admin_action(
        db, request=request, actor=admin, action="support.ticket_assigned",
        capability=Capability.SUPPORT_MANAGE, resource_type="support_ticket",
        resource_id=ticket.id,
        previous_state={"assigned_admin_id": str(previous_id) if previous_id else None},
        resulting_state={
            "assigned_admin_id": str(ticket.assigned_admin_id) if ticket.assigned_admin_id else None
        },
        reason="support_queue_assignment",
    )
    db.commit()
    db.refresh(ticket)
    return _admin_read(ticket)


@router.post("/admin/support/tickets/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
def add_admin_public_message(
    ticket_id: uuid.UUID,
    payload: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.SUPPORT_MANAGE)),
):
    ticket = _locked_ticket(db, ticket_id)
    if ticket.status == "closed":
        raise HTTPException(status_code=409, detail="Closed tickets must be reopened before replying")
    message, created = _add_message(
        db, ticket=ticket, author=admin, visibility="public", payload=payload
    )
    if not created:
        return _public_message(message)
    record_admin_action(
        db, request=request, actor=admin, action="support.public_message_added",
        capability=Capability.SUPPORT_MANAGE, resource_type="support_ticket",
        resource_id=ticket.id, resulting_state={"version": ticket.version},
        reason="customer_visible_support_response",
    )
    enqueue_notification(
        db, user_id=ticket.user_id, event_type="support.public_message",
        title="New support reply", body="GaonOne support replied to your ticket.",
        data={"ticket_id": str(ticket.id)},
    )
    db.commit()
    db.refresh(message)
    return _public_message(message)


@router.post("/admin/support/tickets/{ticket_id}/internal-notes", status_code=status.HTTP_201_CREATED)
def add_internal_note(
    ticket_id: uuid.UUID,
    payload: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_capability(Capability.SUPPORT_MANAGE)),
):
    ticket = _locked_ticket(db, ticket_id)
    message, created = _add_message(
        db, ticket=ticket, author=admin, visibility="internal", payload=payload
    )
    if not created:
        return _internal_message(message)
    record_admin_action(
        db, request=request, actor=admin, action="support.internal_note_added",
        capability=Capability.SUPPORT_MANAGE, resource_type="support_ticket",
        resource_id=ticket.id, resulting_state={"version": ticket.version},
        reason="internal_support_collaboration",
    )
    # Internal notes deliberately never enqueue requester notifications.
    db.commit()
    db.refresh(message)
    return _internal_message(message)
