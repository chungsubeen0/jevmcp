from __future__ import annotations

from collections import defaultdict
from typing import Any

from evals.metrics import band, completion_cost, overconfident, recall_at_k
from evals.schema import GoldenCase


def score_case(case: GoldenCase, result: dict[str, Any]) -> dict[str, Any]:
    if "error" in result:
        return {"id": case.id, "ok": False, "error": result["error"]["code"]}
    signals = result.get("signals") or result.get("answers") or {}
    directional_hits = 0
    directional_total = 0
    overconfident_ambiguous = 0
    for key, expected in case.labels.expected_band.items():
        if key not in signals:
            continue
        directional_total += 1
        actual = band(float(signals[key]))
        if actual == expected:
            directional_hits += 1
        if case.labels.uncertain_expected and overconfident(float(signals[key])):
            overconfident_ambiguous += 1
    status_ok = True
    if case.labels.expected_status and result.get("status") != case.labels.expected_status:
        status_ok = False
    missed = 0
    extra = 0
    if case.category == "check_completion":
        review = set(result.get("review_requirements") or [])
        required = set(case.labels.review_ids)
        missed = len(required - review)
        extra = len(review - required)
    recall10 = None
    if case.category == "rank_context" and case.labels.critical_ids:
        ranked = [row["id"] for row in result.get("candidates", [])]
        recall10 = recall_at_k(ranked, case.labels.critical_ids, 10)
    return {
        "id": case.id,
        "ok": status_ok and (directional_hits == directional_total if directional_total else status_ok),
        "directional_hits": directional_hits,
        "directional_total": directional_total,
        "status_ok": status_ok,
        "overconfident_ambiguous": overconfident_ambiguous,
        "completion_cost": completion_cost(missed_complete=missed, extra_uncertain=extra),
        "missed_requirements": missed,
        "critical_recall_at_10": recall10,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cat[row.get("category", "unknown")].append(row)
    directional_hits = sum(row.get("directional_hits", 0) for row in rows)
    directional_total = sum(row.get("directional_total", 0) for row in rows)
    ambiguous = [row for row in rows if row.get("uncertain_expected")]
    overconfident_n = sum(row.get("overconfident_ambiguous", 0) for row in rows)
    recalls = [row["critical_recall_at_10"] for row in rows if row.get("critical_recall_at_10") is not None]
    return {
        "n": len(rows),
        "directional_accuracy": (directional_hits / directional_total) if directional_total else None,
        "missed_requirement_rate": (
            sum(row.get("missed_requirements", 0) for row in rows) / max(1, len(rows))
        ),
        "completion_asymmetric_cost": sum(row.get("completion_cost", 0) for row in rows),
        "ambiguous_case_overconfidence_rate": (overconfident_n / max(1, len(ambiguous))),
        "critical_recall_at_10": (sum(recalls) / len(recalls)) if recalls else None,
    }
