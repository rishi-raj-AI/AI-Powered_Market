from collections.abc import Mapping

from app.models.orders import DeliveryStatus, OrderStatus


ORDER_TRANSITIONS: Mapping[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PLACED: frozenset({OrderStatus.ACCEPTED, OrderStatus.CANCELLED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.PREPARING, OrderStatus.CANCELLED}),
    OrderStatus.PREPARING: frozenset({OrderStatus.READY}),
    OrderStatus.READY: frozenset({OrderStatus.OUT_FOR_DELIVERY}),
    OrderStatus.OUT_FOR_DELIVERY: frozenset({OrderStatus.DELIVERED}),
}

DELIVERY_TRANSITIONS: Mapping[DeliveryStatus, frozenset[DeliveryStatus]] = {
    DeliveryStatus.UNASSIGNED: frozenset({DeliveryStatus.ASSIGNED}),
    DeliveryStatus.ASSIGNED: frozenset({DeliveryStatus.PICKED_UP}),
    DeliveryStatus.PICKED_UP: frozenset({DeliveryStatus.DELIVERED}),
}


def can_transition_order(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ORDER_TRANSITIONS.get(current, frozenset())


def can_transition_delivery(current: DeliveryStatus, target: DeliveryStatus) -> bool:
    return target in DELIVERY_TRANSITIONS.get(current, frozenset())
