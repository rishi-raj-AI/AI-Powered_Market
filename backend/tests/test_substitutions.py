from decimal import Decimal

from app.api.v1.routes.substitutions import _substitution_score


def test_substitution_score_prefers_close_price_and_same_brand():
    base = Decimal('100.00')
    close_other = _substitution_score(base, Decimal('105.00'), False)
    close_same = _substitution_score(base, Decimal('105.00'), True)
    far_same = _substitution_score(base, Decimal('180.00'), True)
    assert close_same > close_other
    assert close_other > far_same
