from jev_mcp.errors import JevError
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.judge import reject_generative, run_judge


async def test_judge_returns_answers(engine):
    result = await run_judge(
        engine,
        state={"failure": "null guest id"},
        questions=[{"id": "Q1", "question": "Does the supplied evidence suggest a null identity?"}],
    )
    assert "Q1" in result["answers"]
    assert 0.0 <= result["answers"]["Q1"] <= 1.0


async def test_judge_rejects_generative():
    try:
        reject_generative("write this function for guest checkout")
        raised = False
    except JevError as exc:
        raised = True
        assert exc.code.value == "INVALID_INPUT"
    assert raised


async def test_judge_allows_evidence_question():
    reject_generative("Does the supplied evidence suggest we still lack tests?")


async def test_judge_uses_mock_provider(app_config):
    engine = __import__("jev_mcp.engine", fromlist=["Engine"]).Engine.create(
        app_config, provider=MockJudgmentProvider(answers={"Q1": 0.87})
    )
    result = await run_judge(
        engine,
        state={"x": 1},
        questions=[{"id": "Q1", "question": "Does the supplied evidence suggest X?"}],
    )
    assert result["answers"]["Q1"] == 0.87
