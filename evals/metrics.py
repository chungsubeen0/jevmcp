from __future__ import annotations

import math


def band(probability: float, low: float = 0.30, high: float = 0.70) -> str:
    if probability <= low:
        return "LOW"
    if probability >= high:
        return "HIGH"
    return "UNCERTAIN"


def recall_at_k(ranked_ids: list[str], critical: list[str], k: int) -> float:
    if not critical:
        return 1.0
    top = set(ranked_ids[:k])
    return sum(1 for item in critical if item in top) / len(critical)


def mean_reciprocal_rank(ranked_ids: list[str], critical: list[str]) -> float:
    if not critical:
        return 1.0
    ranks = []
    for item in critical:
        try:
            ranks.append(1.0 / (ranked_ids.index(item) + 1))
        except ValueError:
            ranks.append(0.0)
    return sum(ranks) / len(ranks)


def dcg(gains: list[float]) -> float:
    return sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))


def ndcg(ranked_tiers: list[str], ideal_tiers: list[str]) -> float:
    weight = {"HIGH": 3.0, "MEDIUM": 1.0, "LOW": 0.0}
    actual = dcg([weight.get(tier, 0.0) for tier in ranked_tiers])
    ideal = dcg([weight.get(tier, 0.0) for tier in ideal_tiers])
    if ideal == 0:
        return 1.0
    return actual / ideal


def completion_cost(*, missed_complete: int, extra_uncertain: int) -> int:
    return missed_complete * 5 + extra_uncertain * 1


def overconfident(probability: float, *, low: float = 0.30, high: float = 0.70) -> bool:
    return probability <= low or probability >= high
