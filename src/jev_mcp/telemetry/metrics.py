from __future__ import annotations


def probability_summary(answers: dict[str, float]) -> dict[str, float]:
    if not answers:
        return {"count": 0.0, "min": 0.0, "max": 0.0, "mean": 0.0}
    values = list(answers.values())
    return {
        "count": float(len(values)),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
    }
