from __future__ import annotations

import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def mcp_session(tmp_path: Path, *, extra_env: dict[str, str] | None = None) -> AsyncIterator[Any]:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    env = os.environ.copy()
    env.update(
        {
            "JEV_MCP_PROVIDER": "mock",
            "JEV_MCP_PROFILE": "interactive",
            "JEV_MCP_SHADOW_MODE": "true",
            "JEV_MCP_DATA_DIR": str(tmp_path),
            "JEV_MCP_LOG_LEVEL": "WARNING",
            "PYTHONPATH": str(REPO / "src") + os.pathsep + env.get("PYTHONPATH", ""),
        }
    )
    env.pop("TYPESAFE_API_KEY", None)
    if extra_env:
        env.update(extra_env)
        if extra_env.get("JEV_MCP_TEST_FAULT"):
            env["JEV_MCP_ALLOW_FAULTS"] = "1"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "jev_mcp", "--provider", extra_env.get("JEV_MCP_PROVIDER", "mock") if extra_env else "mock"],
        env=env,
        cwd=str(REPO),
    )
    async with stdio_client(params) as streams:
        read, write = streams[:2]
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def parse_tool_result(result: Any) -> dict[str, Any]:
    if hasattr(result, "structuredContent") and result.structuredContent:
        return result.structuredContent
    content = getattr(result, "content", None) or []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            return json.loads(text)
    if isinstance(result, dict):
        return result
    raise AssertionError(f"unparseable MCP result: {result!r}")
