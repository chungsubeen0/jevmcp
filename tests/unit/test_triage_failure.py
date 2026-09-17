from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.triage_failure import run_triage_failure


async def test_local_related_failure_is_classified(app_config):
    provider = MockJudgmentProvider(
        answers={
            "related_to_current_change": 0.97,
            "likely_localized": 0.89,
            "likely_preexisting": 0.04,
            "requirement_related": 0.94,
            "same_as_previous_failure": 0.10,
            "needs_deeper_reasoning": 0.22,
        }
    )
    engine = Engine.create(app_config, provider=provider)
    result = await run_triage_failure(
        engine,
        task={"goal": "guest checkout", "requirements": [{"id": "R14", "text": "canonical user"}]},
        current_step="webhook identity",
        failure={
            "command": "pnpm test",
            "exit_code": 1,
            "summary": "guest_identity null",
            "output": "FAIL stripe.test.ts guest_identity expected UUID",
        },
        changed_files=["src/webhooks/stripe.ts"],
        diff_summary="resolveGuest returns null",
    )
    assert result["classification"]["relationship"] == "LIKELY_RELATED"
    assert result["classification"]["scope"] == "LIKELY_LOCAL"
    assert result["classification"]["escalation"] == "NORMAL"


async def test_unrelated_environment_failure(app_config):
    provider = MockJudgmentProvider(
        answers={
            "related_to_current_change": 0.08,
            "likely_localized": 0.12,
            "likely_preexisting": 0.88,
            "requirement_related": 0.05,
            "same_as_previous_failure": 0.20,
            "needs_deeper_reasoning": 0.41,
        }
    )
    engine = Engine.create(app_config, provider=provider)
    result = await run_triage_failure(
        engine,
        task={"goal": "button padding", "requirements": []},
        current_step="css",
        failure={"command": "pytest", "exit_code": 1, "summary": "postgres timeout", "output": "ETIMEDOUT"},
        changed_files=["src/ui/Button.tsx"],
        diff_summary="padding 8px -> 12px",
    )
    assert result["classification"]["relationship"] == "LIKELY_UNRELATED"
