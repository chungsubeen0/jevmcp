from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.compare_attempts import run_compare_attempts


async def test_repeated_failure_becomes_stuck(app_config):
    provider = MockJudgmentProvider(
        answers={
            "same_failure": 0.94,
            "same_strategy": 0.91,
            "meaningful_new_evidence": 0.12,
            "meaningful_progress": 0.18,
            "reconsider_approach": 0.93,
        }
    )
    engine = Engine.create(app_config, provider=provider)
    result = await run_compare_attempts(
        engine,
        task_goal="Fix guest identity resolution",
        previous_attempt={
            "hypothesis": "Normalize email before lookup",
            "approach": "Normalize email before lookup",
            "failure": "user_id remains null",
        },
        current_attempt={
            "hypothesis": "Normalize email earlier",
            "approach": "Normalize email earlier before same lookup",
            "failure": "user_id remains null",
        },
    )
    assert result["status"] == "LIKELY_STUCK"
    assert result["control_signal"] == "REASSESS"
    assert "user should change the hypothesis" in result["user_decision"]


async def test_advanced_failure_is_not_stuck(app_config):
    provider = MockJudgmentProvider(
        answers={
            "same_failure": 0.18,
            "same_strategy": 0.22,
            "meaningful_new_evidence": 0.88,
            "meaningful_progress": 0.81,
            "reconsider_approach": 0.20,
        }
    )
    engine = Engine.create(app_config, provider=provider)
    result = await run_compare_attempts(
        engine,
        task_goal="Restore database",
        previous_attempt={"approach": "connect", "failure": "connection refused"},
        current_attempt={"approach": "migrate", "failure": "UNIQUE constraint"},
    )
    assert result["status"] == "PROGRESSING"
    assert result["control_signal"] == "CONTINUE"
    assert "predefined goal" in result["user_decision"]
