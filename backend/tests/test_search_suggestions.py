from app.api.v1.routes.search_suggestions import _prefix_rank


def test_prefix_rank_prefers_exact_then_prefix_then_contains():
    assert _prefix_rank('Milk', 'milk') == 0
    assert _prefix_rank('Milk powder', 'milk') == 1
    assert _prefix_rank('Fresh milk', 'milk') == 2
    assert _prefix_rank('Bread', 'milk') == 99


def test_prefix_rank_handles_missing_values():
    assert _prefix_rank(None, 'milk') == 99
