from app.api.v1.routes.reorder import _available_quantity


def test_available_quantity_clamps_to_stock_and_requested():
    assert _available_quantity(10, 3, True) == 3
    assert _available_quantity(2, 5, True) == 2


def test_available_quantity_rejects_disabled_or_empty_stock():
    assert _available_quantity(10, 3, False) == 0
    assert _available_quantity(0, 3, True) == 0
