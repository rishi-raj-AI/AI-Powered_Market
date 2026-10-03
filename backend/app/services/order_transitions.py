from collections.abc import Mapping

from app.models.orders import Delivery, DeliveryStatus, Order, OrderStatus, PaymentMethod, PaymentStatus

ORDER_TRANSITIONS: Mapping[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PLACED: frozenset({OrderStatus.ACCEPTED, OrderStatus.CANCELLED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.PREPARING, OrderStatus.CANCELLED}),
    OrderStatus.PREPARING: frozenset({OrderStatus.READY}),
    OrderStatus.READY: frozenset({OrderStatus.OUT_FOR_DELIVERY}),
    # RETURNED is the only exit from a delivery that failed after pickup. It is
    # reachable exclusively through the admin failure-resolution endpoint;
    # merchant-facing status updates reject it explicitly.
    OrderStatus.OUT_FOR_DELIVERY: frozenset({OrderStatus.DELIVERED, OrderStatus.RETURNED}),
}

#: Statuses a merchant may drive from their own order screen. Everything else
#: is an operations decision with financial consequences.
MERCHANT_ASSIGNABLE_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.ACCEPTED,
        OrderStatus.PREPARING,
        OrderStatus.READY,
        OrderStatus.CANCELLED,
    }
)

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


def payment_allows_fulfillment(order: Order) -> bool:
    """Whether an order may enter or continue physical delivery.

    COD has no online payment to confirm and is settled only after its exact
    server-recorded collection. Every non-COD order must have a confirmed
    payment before the merchant/rider workflow can release goods.
    """
    return order.payment_method == PaymentMethod.COD or order.payment_status == PaymentStatus.PAID


def transition_order(order: Order, target: OrderStatus) -> None:
    if not can_transition_order(order.status, target):
        raise ValueError(f"Invalid order transition from {order.status.value} to {target.value}")
    order.status = target


def transition_delivery(delivery: Delivery, target: DeliveryStatus) -> None:
    if not can_transition_delivery(delivery.status, target):
        raise ValueError(f"Invalid delivery transition from {delivery.status.value} to {target.value}")
    delivery.status = target
