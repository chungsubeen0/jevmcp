from jev_mcp.engine import Engine
from jev_mcp.models import JudgmentQuestion
from jev_mcp.providers.mock import MockProvider


async def test_identical_state_is_cached(app_config):
    provider = MockProvider(answers={"Q1": 0.77})
    engine = Engine.create(app_config, provider=provider)
    questions = [JudgmentQuestion(id="Q1", question="Does evidence suggest X?")]
    state = {"hello": "world"}
    first, cached_first, _ = await engine.evaluate(
        tool="jev_judge",
        tool_version="1.0.0",
        state=state,
        questions=questions,
    )
    second, cached_second, _ = await engine.evaluate(
        tool="jev_judge",
        tool_version="1.0.0",
        state=state,
        questions=questions,
    )
    assert cached_first is False
    assert cached_second is True
    assert first.answers == second.answers
    assert len(provider.calls) == 1


async def test_cache_bypassed_when_disabled(app_config):
    provider = MockProvider(answers={"Q1": 0.4})
    engine = Engine.create(app_config, provider=provider)
    questions = [JudgmentQuestion(id="Q1", question="Does evidence suggest X?")]
    await engine.evaluate(
        tool="jev_judge",
        tool_version="1.0.0",
        state={"a": 1},
        questions=questions,
        use_cache=False,
    )
    await engine.evaluate(
        tool="jev_judge",
        tool_version="1.0.0",
        state={"a": 1},
        questions=questions,
        use_cache=False,
    )
    assert len(provider.calls) == 2
