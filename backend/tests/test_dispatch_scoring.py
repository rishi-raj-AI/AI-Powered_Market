from app.services.dispatch_scoring import batch_ready_deliveries, rank_candidates, score_candidate


def test_dispatch_score_prefers_nearer_candidate() -> None:
    near = score_candidate(rider_id="near", distance_km=1.2, location_age_seconds=120)
    far = score_candidate(rider_id="far", distance_km=2.0, location_age_seconds=1)
    assert rank_candidates([far, near])[0].rider_id == "near"


def test_freshness_breaks_close_distance_ties() -> None:
    stale = score_candidate(rider_id="stale", distance_km=1.0, location_age_seconds=240)
    fresh = score_candidate(rider_id="fresh", distance_km=1.0, location_age_seconds=10)
    assert rank_candidates([stale, fresh])[0].rider_id == "fresh"


def test_dispatch_batching_is_bounded_and_stable() -> None:
    ids = [str(index) for index in range(45)]
    batches = batch_ready_deliveries(ids, max_batch_size=20)
    assert [len(batch) for batch in batches] == [20, 20, 5]
    assert [item for batch in batches for item in batch] == ids
