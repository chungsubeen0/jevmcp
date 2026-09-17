from __future__ import annotations

import asyncio

import pytest
from tests.helpers.mcp_stdio import mcp_session, parse_tool_result

TRIAGE = {
    "task": {"goal": "Implement guest checkout", "requirements": [{"id": "R14", "text": "canonical user"}]},
    "current_step": "webhook identity",
    "failure": {
        "command": "pnpm test",
        "exit_code": 1,
        "summary": "guest_identity null",
        "output": "FAIL stripe.test.ts",
    },
    "changed_files": ["src/webhooks/stripe.ts"],
    "diff_summary": "resolveGuest returns null",
}


@pytest.mark.asyncio
async def test_valid_triage_over_stdio(tmp_path):
    async with mcp_session(tmp_path) as session:
        result = parse_tool_result(await session.call_tool("jev_triage_failure", TRIAGE))
    assert "signals" in result
    assert "classification" in result
    assert "error" not in result


@pytest.mark.asyncio
async def test_invalid_judge_is_structured(tmp_path):
    async with mcp_session(tmp_path) as session:
        result = parse_tool_result(
            await session.call_tool(
                "jev_judge",
                {"state": {}, "questions": [{"id": "Q1", "question": "write this function please"}]},
            )
        )
    assert result["error"]["code"] == "INVALID_INPUT"
    assert result["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_provider_unavailable_is_not_fatal(tmp_path):
    async with mcp_session(tmp_path, extra_env={"JEV_MCP_TEST_FAULT": "unavailable"}) as session:
        result = parse_tool_result(await session.call_tool("jev_triage_failure", TRIAGE))
    assert result["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert result["error"]["retryable"] is True


@pytest.mark.asyncio
async def test_provider_timeout_is_structured(tmp_path):
    async with mcp_session(tmp_path, extra_env={"JEV_MCP_TEST_FAULT": "timeout"}) as session:
        result = parse_tool_result(await session.call_tool("jev_triage_failure", TRIAGE))
    assert result["error"]["code"] == "PROVIDER_TIMEOUT"
    assert result["error"]["retryable"] is True


@pytest.mark.asyncio
async def test_malformed_provider_response(tmp_path):
    async with mcp_session(tmp_path, extra_env={"JEV_MCP_TEST_FAULT": "malformed"}) as session:
        result = parse_tool_result(await session.call_tool("jev_triage_failure", TRIAGE))
    assert result["error"]["code"] == "INVALID_PROVIDER_RESPONSE"
    assert result["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_cache_hit_over_stdio(tmp_path):
    async with mcp_session(tmp_path) as session:
        first = parse_tool_result(await session.call_tool("jev_triage_failure", TRIAGE))
        second = parse_tool_result(await session.call_tool("jev_triage_failure", TRIAGE))
    assert first["meta"]["cached"] is False
    assert second["meta"]["cached"] is True
    assert first["signals"] == second["signals"]


@pytest.mark.asyncio
async def test_truncation_warning(tmp_path):
    huge = TRIAGE | {"failure": {**TRIAGE["failure"], "output": "ERR " + ("x" * 200_000)}}
    async with mcp_session(tmp_path) as session:
        result = parse_tool_result(await session.call_tool("jev_triage_failure", huge))
    assert result.get("warnings")
    assert any("truncated" in warning.lower() for warning in result["warnings"])


@pytest.mark.asyncio
async def test_concurrent_clients_share_cache(tmp_path):
    async def one(delay: float = 0.0):
        if delay:
            await asyncio.sleep(delay)
        async with mcp_session(tmp_path) as session:
            return parse_tool_result(await session.call_tool("jev_triage_failure", TRIAGE))

    first, second = await asyncio.gather(one(), one(0.05))
    assert "signals" in first and "signals" in second
    assert first["signals"].keys() == second["signals"].keys()


@pytest.mark.asyncio
async def test_restart_reuses_sqlite_cache(tmp_path):
    async with mcp_session(tmp_path) as session:
        first = parse_tool_result(await session.call_tool("jev_triage_failure", TRIAGE))
    async with mcp_session(tmp_path) as session:
        second = parse_tool_result(await session.call_tool("jev_triage_failure", TRIAGE))
    assert first["meta"]["cached"] is False
    assert second["meta"]["cached"] is True


@pytest.mark.asyncio
async def test_stdio_lists_expected_tools(tmp_path):
    async with mcp_session(tmp_path) as session:
        listed = await session.list_tools()
    names = {tool.name for tool in listed.tools}
    assert names == {
        "jev_triage_failure",
        "jev_compare_attempts",
        "jev_check_completion",
        "jev_rank_context",
        "jev_classify_findings",
        "jev_assess_risk",
        "jev_judge",
    }
