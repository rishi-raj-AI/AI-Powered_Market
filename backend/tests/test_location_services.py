from app.services.places import distance_km


def test_distance_km_is_zero_for_same_point() -> None:
    assert distance_km(20.0778, 73.7898, 20.0778, 73.7898) == 0


def test_distance_km_returns_reasonable_local_distance() -> None:
    value = distance_km(20.0778, 73.7898, 20.0878, 73.7898)
    assert 1.0 < value < 1.2
