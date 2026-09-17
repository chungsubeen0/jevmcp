from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.rank_context import run_rank_context


async def test_rank_keeps_all_candidates(app_config):
    provider = MockJudgmentProvider(
        answers={
            "C1::relevant_to_task": 0.96,
            "C1::useful_now": 0.91,
            "C1::likely_noise": 0.03,
            "C2::relevant_to_task": 0.08,
            "C2::useful_now": 0.05,
            "C2::likely_noise": 0.92,
        }
    )
    engine = Engine.create(app_config, provider=provider)
    result = await run_rank_context(
        engine,
        task_goal="webhook identity",
        current_step="inspect helpers",
        candidates=[
            {"id": "C1", "path": "src/webhooks/stripe.ts", "symbol": "resolveUser", "content": "fn"},
            {"id": "C2", "path": "README.md", "content": "welcome"},
        ],
    )
    ids = {row["id"] for row in result["candidates"]}
    assert ids == {"C1", "C2"}
    by_id = {row["id"]: row for row in result["candidates"]}
    assert by_id["C1"]["tier"] == "HIGH"
    assert by_id["C2"]["tier"] == "LOW"
