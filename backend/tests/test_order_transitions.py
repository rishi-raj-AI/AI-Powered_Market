from app.models.orders import DeliveryStatus, OrderStatus
from app.services.order_transitions import can_transition_delivery, can_transition_order


def test_order_transition_policy() -> None:
    assert can_transition_order(OrderStatus.PLACED, OrderStatus.ACCEPTED)
    assert can_transition_order(OrderStatus.PLACED, OrderStatus.CANCELLED)
    assert can_transition_order(OrderStatus.ACCEPTED, OrderStatus.PREPARING)
    assert can_transition_order(OrderStatus.PREPARING, OrderStatus.READY)
    assert can_transition_order(OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY)
    assert can_transition_order(OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED)

    assert not can_transition_order(OrderStatus.PLACED, OrderStatus.READY)
    assert not can_transition_order(OrderStatus.READY, OrderStatus.DELIVERED)
    assert not can_transition_order(OrderStatus.DELIVERED, OrderStatus.CANCELLED)


def test_delivery_transition_policy() -> None:
    assert can_transition_delivery(DeliveryStatus.UNASSIGNED, DeliveryStatus.ASSIGNED)
    assert can_transition_delivery(DeliveryStatus.ASSIGNED, DeliveryStatus.PICKED_UP)
    assert can_transition_delivery(DeliveryStatus.PICKED_UP, DeliveryStatus.DELIVERED)

    assert not can_transition_delivery(DeliveryStatus.UNASSIGNED, DeliveryStatus.PICKED_UP)
    assert not can_transition_delivery(DeliveryStatus.ASSIGNED, DeliveryStatus.DELIVERED)
    assert not can_transition_delivery(DeliveryStatus.DELIVERED, DeliveryStatus.PICKED_UP)
