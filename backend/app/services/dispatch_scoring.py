from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DispatchCandidateScore:
    rider_id: str
    distance_km: float
    location_age_seconds: int
    score: float


def score_candidate(*, rider_id: str, distance_km: float, location_age_seconds: int) -> DispatchCandidateScore:
    """Deterministic V1 score; lower is better.

    Distance remains dominant. Location freshness only breaks close calls and
    never makes an ineligible rider eligible.
    """
    distance = max(0.0, float(distance_km))
    age = max(0, int(location_age_seconds))
    score = round(distance + min(age, 300) / 3000.0, 6)
    return DispatchCandidateScore(rider_id=rider_id, distance_km=distance, location_age_seconds=age, score=score)


def rank_candidates(candidates: list[DispatchCandidateScore]) -> list[DispatchCandidateScore]:
    return sorted(candidates, key=lambda item: (item.score, item.distance_km, item.rider_id))


def batch_ready_deliveries(delivery_ids: list[str], *, max_batch_size: int = 20) -> list[list[str]]:
    """Bound operational dispatch work without changing assignment semantics."""
    size = max(1, min(int(max_batch_size), 100))
    return [delivery_ids[index : index + size] for index in range(0, len(delivery_ids), size)]
