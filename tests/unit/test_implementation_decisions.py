import pytest

from jev_mcp.errors import ErrorCode, JevError
from jev_mcp.policy.decisions import (
    attempt_user_decision,
    completion_user_decision,
    findings_user_decision,
    rank_user_decision,
    risk_user_decision,
    triage_user_decision,
)
from jev_mcp.tools._common import require_predefined_goal
from jev_mcp.tools.compare_attempts import run_compare_attempts


def test_require_predefined_goal_rejects_blank():
    with pytest.raises(JevError) as exc:
        require_predefined_goal("   ")
    assert exc.value.code == ErrorCode.INVALID_INPUT
    assert "predefined goal" in exc.value.message


def test_require_predefined_goal_keeps_user_goal():
    assert require_predefined_goal("  Ship guest checkout  ") == "Ship guest checkout"


def test_attempt_decisions_do_not_change_the_goal():
    assert "predefined goal" in attempt_user_decision("PROGRESSING", "CONTINUE")
    assert "change the hypothesis" in attempt_user_decision("LIKELY_STUCK", "REASSESS")
    assert "different approach toward the goal" in attempt_user_decision("LIKELY_STUCK", "ESCALATE")
    assert "goal stays fixed" in attempt_user_decision("UNCERTAIN", "CONTINUE")


def test_completion_decision_is_not_a_ship_gate():
    assert "Keep implementing" in completion_user_decision("INCOMPLETE")
    assert "user reviews" in completion_user_decision("REVIEW_REQUIRED")
    assert "Not a ship" in completion_user_decision("APPEARS_COMPLETE")


def test_other_implementation_decisions_stay_advisory():
    assert "Do not skip" in triage_user_decision(
        {"relationship": "LIKELY_RELATED", "escalation": "NORMAL"}
    )
    assert "Do not drop" in rank_user_decision()
    assert "do not confirm" in findings_user_decision()
    assert "Not a security conclusion" in risk_user_decision(True)
    assert "Not a safety certification" in risk_user_decision(False)


async def test_compare_attempts_rejects_missing_goal(app_config):
    from jev_mcp.engine import Engine
    from jev_mcp.providers.mock import MockJudgmentProvider

    engine = Engine.create(app_config, provider=MockJudgmentProvider())
    with pytest.raises(JevError) as exc:
        await run_compare_attempts(
            engine,
            task_goal=" ",
            previous_attempt={"approach": "a", "failure": "x"},
            current_attempt={"approach": "b", "failure": "y"},
        )
    assert exc.value.code == ErrorCode.INVALID_INPUT
