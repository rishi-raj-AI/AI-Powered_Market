from collections.abc import Mapping

from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus

ORDER_TRANSITIONS: Mapping[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PLACED: frozenset({OrderStatus.ACCEPTED, OrderStatus.CANCELLED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.PREPARING, OrderStatus.CANCELLED}),
    OrderStatus.PREPARING: frozenset({OrderStatus.READY}),
    OrderStatus.READY: frozenset({OrderStatus.OUT_FOR_DELIVERY}),
    OrderStatus.OUT_FOR_DELIVERY: frozenset({OrderStatus.DELIVERED}),
}

DELIVERY_TRANSITIONS: Mapping[DeliveryStatus, frozenset[DeliveryStatus]] = {
    DeliveryStatus.UNASSIGNED: frozenset({DeliveryStatus.ASSIGNED}),
    DeliveryStatus.ASSIGNED: frozenset(
        {DeliveryStatus.UNASSIGNED, DeliveryStatus.PICKED_UP, DeliveryStatus.FAILED}
    ),
    DeliveryStatus.PICKED_UP: frozenset({DeliveryStatus.DELIVERED, DeliveryStatus.FAILED}),
    DeliveryStatus.FAILED: frozenset({DeliveryStatus.UNASSIGNED}),
}


def can_transition_order(current: OrderStatus, target: OrderStatus) -> bool:
    return target in ORDER_TRANSITIONS.get(current, frozenset())


def can_transition_delivery(current: DeliveryStatus, target: DeliveryStatus) -> bool:
    return target in DELIVERY_TRANSITIONS.get(current, frozenset())


def transition_order(order: Order, target: OrderStatus) -> None:
    if not can_transition_order(order.status, target):
        raise ValueError(f"Invalid order transition from {order.status.value} to {target.value}")
    order.status = target


def transition_delivery(delivery: Delivery, target: DeliveryStatus) -> None:
    if not can_transition_delivery(delivery.status, target):
        raise ValueError(f"Invalid delivery transition from {delivery.status.value} to {target.value}")
    delivery.status = target
