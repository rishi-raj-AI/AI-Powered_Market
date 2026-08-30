from app.api.v1.routes.basket_recommendations import _basket_score


def test_category_match_is_ranked_above_generic_same_store_item() -> None:
    assert _basket_score(True, 5, 100.0) > _basket_score(False, 5, 100.0)
