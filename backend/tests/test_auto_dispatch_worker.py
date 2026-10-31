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
