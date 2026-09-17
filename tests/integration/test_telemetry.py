from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.judge import run_judge


async def test_telemetry_stores_hashes_not_source(app_config):
    engine = Engine.create(app_config, provider=MockJudgmentProvider(answers={"Q1": 0.4}))
    await run_judge(
        engine,
        state={"source": "def secret(): return 1"},
        questions=[{"id": "Q1", "question": "Does the supplied evidence suggest a function?"}],
    )
    rows = engine.telemetry.export_rows()
    assert rows
    assert rows[0]["content"] is None
    assert rows[0]["state_hash"]
    assert "def secret" not in str(rows[0])
