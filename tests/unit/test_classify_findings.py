from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.classify_findings import run_classify_findings


async def test_classify_findings_signals(app_config):
    provider = MockJudgmentProvider(
        answers={
            "F1::likely_valid": 0.9,
            "F1::requirement_related": 0.1,
            "F1::requires_code_change": 0.7,
            "F1::requires_replan": 0.05,
            "F1::likely_duplicate": 0.1,
            "F1::security_relevant": 0.02,
            "F1::data_integrity_relevant": 0.02,
        }
    )
    engine = Engine.create(app_config, provider=provider)
    result = await run_classify_findings(
        engine,
        task_goal="review",
        findings=[{"id": "F1", "source": "lint", "text": "missing newline"}],
    )
    assert result["findings"][0]["signals"]["likely_valid"] == 0.9
    assert "not confirm" in result["note"].lower()
