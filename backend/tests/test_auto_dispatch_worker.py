"""Regression coverage for unattended dispatch: never invent an assignment."""
from unittest.mock import MagicMock, patch

from app.services.auto_dispatch import dispatch_ready_deliveries


def test_no_ready_deliveries_is_a_noop():
    db = MagicMock()
    db.scalar.return_value = None
    result = dispatch_ready_deliveries(db, limit=5)
    assert result == {"assigned": 0, "skipped": 0}
    db.commit.assert_not_called()


def test_ready_delivery_without_order_is_not_assigned():
    db = MagicMock()
    delivery = MagicMock()
    delivery.id = "delivery-1"
    delivery.order_id = "order-1"
    db.scalar.side_effect = [delivery, None]
    db.get.return_value = None
    result = dispatch_ready_deliveries(db, limit=1)
    assert result == {"assigned": 0, "skipped": 1}
    db.commit.assert_not_called()
    db.rollback.assert_called()


def test_no_eligible_rider_preserves_unassigned_delivery():
    db = MagicMock()
    delivery = MagicMock()
    delivery.id = "delivery-2"
    delivery.order_id = "order-2"
    order = MagicMock()
    order.store_id = "store-2"
    store = MagicMock()
    store.latitude = 18.6
    store.longitude = 73.8
    db.scalar.return_value = delivery
    db.get.side_effect = [order, store]
    with (
        patch("app.services.auto_dispatch.payment_allows_fulfillment", return_value=True),
        patch("app.services.auto_dispatch.nearest_eligible_rider", return_value=None),
    ):
        result = dispatch_ready_deliveries(db, limit=1)
    assert result == {"assigned": 0, "skipped": 1}
    db.commit.assert_not_called()
    db.rollback.assert_called()


def test_successful_auto_assignment_is_audited_and_notified_atomically():
    db = MagicMock()
    delivery = MagicMock()
    delivery.id = "delivery-ready"
    delivery.order_id = "order-ready"
    order = MagicMock()
    order.id = "order-ready"
    order.user_id = "customer-id"
    order.store_id = "store-ready"
    order.order_number = "GO-READY"
    store = MagicMock()
    store.latitude = 18.6
    store.longitude = 73.8
    rider = MagicMock()
    rider.id = "rider-ready"
    rider.full_name = "Rider One"
    db.scalar.side_effect = [delivery, None]
    db.get.side_effect = [order, store, rider]
    with (
        patch("app.services.auto_dispatch.payment_allows_fulfillment", return_value=True),
        patch("app.services.auto_dispatch.nearest_eligible_rider", return_value=("rider-ready", 1.2)),
        patch("app.services.auto_dispatch.transition_delivery") as transition,
        patch("app.services.auto_dispatch.annotate_delivery_transition") as audit,
        patch("app.services.auto_dispatch.enqueue_notification") as notify,
    ):
        result = dispatch_ready_deliveries(db, limit=1)
    assert result == {"assigned": 1, "skipped": 0}
    db.commit.assert_called_once()
    transition.assert_called_once()
    audit.assert_called_once()
    assert audit.call_args.kwargs["reason"] == "background_auto_dispatch"
    assert audit.call_args.kwargs["metadata"]["rider_id"] == "rider-ready"
    assert notify.call_count == 2
