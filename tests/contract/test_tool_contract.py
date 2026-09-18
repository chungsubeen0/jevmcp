from __future__ import annotations

import json
from pathlib import Path

from jev_mcp.config import AppConfig
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.server import init_engine, mcp

EXPECTED_TOOLS = [
    "jev_triage_failure",
    "jev_compare_attempts",
    "jev_check_completion",
    "jev_rank_context",
    "jev_classify_findings",
    "jev_assess_risk",
    "jev_judge",
]

SNAPSHOT = Path(__file__).parent / "snapshots" / "tools.json"


def _schema(tool) -> dict:
    schema = getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None)
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump()
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": schema,
    }


async def test_advertised_tools_match_snapshot():
    init_engine(AppConfig.model_validate({"provider": {"name": "mock"}}), provider=MockJudgmentProvider())
    tools = await mcp.list_tools()
    current = {tool.name: _schema(tool) for tool in tools}
    assert sorted(current) == sorted(EXPECTED_TOOLS)
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current == snapshot


async def test_descriptions_are_agent_facing():
    init_engine(AppConfig.model_validate({"provider": {"name": "mock"}}), provider=MockJudgmentProvider())
    tools = {tool.name: tool.description for tool in await mcp.list_tools()}
    assert "before" in tools["jev_triage_failure"].lower()
    compare = tools["jev_compare_attempts"].lower()
    completion = tools["jev_check_completion"].lower()
    assert "unsuccessful" in compare or "next" in compare
    assert "never certifies" in completion or "does not" in completion
    assert "rank" in tools["jev_rank_context"].lower()
    assert "generative" in tools["jev_judge"].lower()
    for name in (
        "jev_triage_failure",
        "jev_compare_attempts",
        "jev_check_completion",
        "jev_rank_context",
        "jev_classify_findings",
        "jev_assess_risk",
    ):
        assert "predefined goal" in tools[name].lower()
