from app.api.v1.routes.personalized_feed import _history_weight


def test_history_weight_rewards_repeat_orders_and_caps_growth() -> None:
    assert _history_weight(0, 0) == 0
    assert _history_weight(2, 3) > _history_weight(1, 1)
    assert _history_weight(100, 100) == 6.0
