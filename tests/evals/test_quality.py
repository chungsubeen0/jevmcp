from evals.quality import _agent_harm
from evals.schema import GoldenCase, Labels


def test_spec_follow_never_drops_ranked_candidates():
    case = GoldenCase(
        id="r1",
        category="rank_context",
        task="x",
        input={},
        labels=Labels(critical_ids=["C1", "C2"]),
    )
    result = {
        "candidates": [
            {"id": "C1", "tier": "MEDIUM"},
            {"id": "C2", "tier": "LOW"},
            {"id": "C3", "tier": "HIGH"},
        ]
    }
    harm = _agent_harm(case, result)
    assert harm["spec"]["critical_dropped"] == 0
    assert harm["blind"]["critical_dropped"] == 2


def test_spec_follow_counts_missing_review_ids_only():
    case = GoldenCase(
        id="c1",
        category="check_completion",
        task="x",
        input={},
        labels=Labels(review_ids=["R3", "R4"], expected_status="REVIEW_REQUIRED"),
    )
    result = {"status": "REVIEW_REQUIRED", "review_requirements": ["R3", "R4"]}
    harm = _agent_harm(case, result)
    assert harm["spec"]["missed_requirements"] == 0
    assert harm["blind"]["missed_requirements"] == 2
