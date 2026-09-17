from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.check_completion import run_check_completion


async def test_subtle_gap_is_not_approved(app_config):
    provider = MockJudgmentProvider(
        answers={
            "R1::appears_satisfied": 0.96,
            "R1::evidence_present": 0.93,
            "R1::possible_gap": 0.04,
            "R2::appears_satisfied": 0.91,
            "R2::evidence_present": 0.88,
            "R2::possible_gap": 0.08,
            "R3::appears_satisfied": 0.40,
            "R3::evidence_present": 0.22,
            "R3::possible_gap": 0.81,
            "R4::appears_satisfied": 0.51,
            "R4::evidence_present": 0.48,
            "R4::possible_gap": 0.49,
            "scope_appropriate": 0.80,
            "unresolved_requirement": 0.78,
            "further_review_warranted": 0.74,
        }
    )
    engine = Engine.create(app_config, provider=provider)
    result = await run_check_completion(
        engine,
        task={
            "goal": "guest checkout",
            "requirements": [
                {"id": "R1", "text": "canonical user"},
                {"id": "R2", "text": "receipt test exists"},
                {"id": "R3", "text": "refund path"},
                {"id": "R4", "text": "audit log"},
            ],
        },
        implementation={"changed_files": ["checkout.ts"], "diff_summary": "guest user"},
        verification={"tests": "identity ok"},
    )
    assert result["status"] in {"INCOMPLETE", "REVIEW_REQUIRED"}
    assert "R3" in result["review_requirements"]
    assert result["status"] not in {"APPROVED", "CORRECT", "SAFE_TO_MERGE", "SECURE"}
