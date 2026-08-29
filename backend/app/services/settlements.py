from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commerce import Store
from app.models.integrations import SettlementEntry
from app.models.orders import Order, PaymentStatus


def ensure_settlement_entry(db: Session, order: Order) -> SettlementEntry:
    existing = db.scalar(
        select(SettlementEntry).where(SettlementEntry.order_id == order.id).with_for_update()
    )
    if existing is not None:
        return existing
    if order.payment_status != PaymentStatus.PAID:
        raise ValueError("Settlement entry requires a paid order")
    store = db.get(Store, order.store_id)
    if store is None:
        raise ValueError("Settlement entry requires a valid store")
    entry = SettlementEntry(
        order_id=order.id,
        store_id=store.id,
        merchant_id=store.merchant_id,
        payment_method=order.payment_method.value,
        gross_amount=order.total,
        merchant_amount=order.subtotal,
        delivery_fee_amount=order.delivery_fee,
        status="pending",
    )
    db.add(entry)
    db.flush()
    return entry
