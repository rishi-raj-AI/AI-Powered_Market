from datetime import datetime, time, timezone
from types import SimpleNamespace

from app.api.v1.routes.basket_recommendations import _basket_score
from app.api.v1.routes.order_recovery import _recovery_actions
from app.api.v1.routes.personalized_feed import _history_weight
from app.api.v1.routes.store_availability import INDIA_TZ, _availability
from app.models.orders import DeliveryStatus, OrderStatus, PaymentMethod, PaymentStatus


def test_personal_history_weight_is_bounded() -> None:
    assert _history_weight(2, 3) > _history_weight(1, 1)
    assert _history_weight(100, 100) == 6.0


def test_basket_score_prefers_category_match() -> None:
    assert _basket_score(True, 5, 100.0) > _basket_score(False, 5, 100.0)


def test_store_availability_reports_minutes_until_close() -> None:
    store = SimpleNamespace(opens_at=time(9, 0), closes_at=time(21, 0))
    now = datetime(2026, 8, 30, 12, 0, tzinfo=INDIA_TZ)
    state = _availability(store, now)
    assert state["is_open"] is True
    assert state["minutes_until_close"] == 540


def test_order_recovery_prioritizes_failed_delivery_support() -> None:
    now = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    order = SimpleNamespace(
        status=OrderStatus.OUT_FOR_DELIVERY,
        payment_method=PaymentMethod.COD,
        payment_status=PaymentStatus.PENDING,
        updated_at=now,
    )
    delivery = SimpleNamespace(status=DeliveryStatus.FAILED)
    actions = _recovery_actions(order, delivery, now)
    assert actions[0]["code"] == "contact_support"
