"""Order pricing. The backend is the only authority for what an order costs.

The delivery fee used to be a literal in two checkout paths, so changing it
meant a code change and the two paths could drift apart. It now resolves from
the service area the store belongs to, falling back to a configured default —
still entirely backend-side, but operable without a deploy and per-area, which
is what a platform spanning villages and towns actually needs.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.commerce import Store
from app.models.geography import ServiceArea

CENTS = Decimal("0.01")


def resolve_delivery_fee(db: Session, store: Store) -> Decimal:
    """The fee for delivering from this store, quantised to paise."""
    fee: Decimal | None = None
    if store.service_area_id is not None:
        area = db.get(ServiceArea, store.service_area_id)
        if area is not None and area.delivery_fee is not None:
            fee = Decimal(area.delivery_fee)
    if fee is None:
        fee = Decimal(settings.DEFAULT_DELIVERY_FEE)
    return fee.quantize(CENTS)


def order_total(subtotal: Decimal, delivery_fee: Decimal) -> Decimal:
    return (Decimal(subtotal) + Decimal(delivery_fee)).quantize(CENTS)
