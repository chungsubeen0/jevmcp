from jev_mcp.config import AppConfig
from jev_mcp.engine import Engine
from jev_mcp.models import JudgmentQuestion
from jev_mcp.providers.mock import MockProvider


async def test_sqlite_cache_survives_engine_rebuild(tmp_path):
    config = AppConfig.model_validate(
        {
            "provider": {"name": "mock"},
            "data_dir": str(tmp_path),
            "cache": {"enabled": True, "ttl_seconds": 3600},
        }
    )
    provider = MockProvider(answers={"Q1": 0.66})
    first = Engine.create(config, provider=provider)
    await first.evaluate(
        tool="jev_judge",
        tool_version="1.0.0",
        state={"k": "v"},
        questions=[JudgmentQuestion(id="Q1", question="Does evidence suggest X?")],
    )
    await first.close()

    second_provider = MockProvider(answers={"Q1": 0.11})
    second = Engine.create(config, provider=second_provider)
    result, cached, _ = await second.evaluate(
        tool="jev_judge",
        tool_version="1.0.0",
        state={"k": "v"},
        questions=[JudgmentQuestion(id="Q1", question="Does evidence suggest X?")],
    )
    assert cached is True
    assert result.answers["Q1"] == 0.66
    assert second_provider.calls == []
    await second.close()
