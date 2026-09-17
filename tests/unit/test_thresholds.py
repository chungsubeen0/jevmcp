import pytest

from jev_mcp.models import ProbabilityBands, StuckThresholds
from jev_mcp.policy.decisions import band, completion_status, stuck_decision
from jev_mcp.policy.profiles import INTERACTIVE

STUCK = StuckThresholds()


def _signals(
    *,
    same_failure: float = 0.90,
    same_strategy: float = 0.85,
    meaningful_new_evidence: float = 0.10,
    meaningful_progress: float = 0.10,
    reconsider_approach: float = 0.40,
) -> dict[str, float]:
    return {
        "same_failure": same_failure,
        "same_strategy": same_strategy,
        "meaningful_new_evidence": meaningful_new_evidence,
        "meaningful_progress": meaningful_progress,
        "reconsider_approach": reconsider_approach,
    }


@pytest.mark.parametrize(
    ("same_failure", "expect_stuck"),
    [(0.8499, False), (0.8500, True), (0.8501, True)],
)
def test_same_failure_boundary(same_failure: float, expect_stuck: bool):
    status, _ = stuck_decision(_signals(same_failure=same_failure), STUCK, INTERACTIVE)
    assert (status == "LIKELY_STUCK") is expect_stuck


@pytest.mark.parametrize(
    ("same_strategy", "expect_stuck"),
    [(0.7999, False), (0.8000, True), (0.8001, True)],
)
def test_same_strategy_boundary(same_strategy: float, expect_stuck: bool):
    status, _ = stuck_decision(_signals(same_strategy=same_strategy), STUCK, INTERACTIVE)
    assert (status == "LIKELY_STUCK") is expect_stuck


@pytest.mark.parametrize(
    ("progress", "expect_stuck"),
    [(0.2999, True), (0.3000, True), (0.3001, False)],
)
def test_progress_boundary(progress: float, expect_stuck: bool):
    status, _ = stuck_decision(_signals(meaningful_progress=progress), STUCK, INTERACTIVE)
    assert (status == "LIKELY_STUCK") is expect_stuck


@pytest.mark.parametrize(
    ("new_evidence", "expect_stuck"),
    [(0.2999, True), (0.3000, True), (0.3001, False)],
)
def test_new_evidence_boundary(new_evidence: float, expect_stuck: bool):
    status, _ = stuck_decision(_signals(meaningful_new_evidence=new_evidence), STUCK, INTERACTIVE)
    assert (status == "LIKELY_STUCK") is expect_stuck


@pytest.mark.parametrize(
    ("same_failure", "same_strategy", "progress", "new_evidence", "expect_stuck"),
    [
        (0.90, 0.85, 0.10, 0.10, True),
        (0.90, 0.85, 0.10, 0.40, False),
        (0.90, 0.85, 0.40, 0.10, False),
        (0.90, 0.70, 0.10, 0.10, False),
        (0.80, 0.85, 0.10, 0.10, False),
    ],
    ids=[
        "all-met",
        "new-evidence-breaks-stuck",
        "progress-breaks-stuck",
        "strategy-breaks-stuck",
        "failure-breaks-stuck",
    ],
)
def test_stuck_combinations(
    same_failure: float,
    same_strategy: float,
    progress: float,
    new_evidence: float,
    expect_stuck: bool,
):
    status, _ = stuck_decision(
        _signals(
            same_failure=same_failure,
            same_strategy=same_strategy,
            meaningful_progress=progress,
            meaningful_new_evidence=new_evidence,
        ),
        STUCK,
        INTERACTIVE,
    )
    assert (status == "LIKELY_STUCK") is expect_stuck


def test_default_bands():
    bands = ProbabilityBands()
    assert band(0.10, bands) == "LOW"
    assert band(0.50, bands) == "UNCERTAIN"
    assert band(0.80, bands) == "HIGH"


def test_completion_never_uses_forbidden_words():
    status, review = completion_status(
        {"R1": {"appears_satisfied": 0.2, "evidence_present": 0.2, "possible_gap": 0.9}},
        {"unresolved_requirement": 0.9, "further_review_warranted": 0.8},
        ProbabilityBands(),
    )
    assert status == "INCOMPLETE"
    assert "R1" in review
    assert status not in {"APPROVED", "CORRECT", "SAFE_TO_MERGE", "SECURE"}
