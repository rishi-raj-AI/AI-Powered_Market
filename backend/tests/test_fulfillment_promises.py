from app.api.v1.routes.fulfillment import _eta_band


def test_eta_band_is_conservative_and_monotonic():
    near = _eta_band(1.0)
    far = _eta_band(12.0)
    assert near[0] >= 28
    assert near[1] - near[0] == 15
    assert far[0] > near[0]
    assert far[1] > far[0]
