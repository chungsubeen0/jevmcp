"""Experiment-only Jev MCP entry point with a strict tool allowlist."""

from __future__ import annotations

import os

from jev_mcp import server

ENV_NAME = "JEV_MCP_EXPERIMENT_TOOLS"


def main() -> None:
    allowed = {name for name in os.environ.get(ENV_NAME, "").split(",") if name}
    if not allowed:
        raise RuntimeError(f"{ENV_NAME} must contain at least one tool")
    registered = {tool.name for tool in server.mcp._tool_manager.list_tools()}
    unknown = allowed - registered
    if unknown:
        raise RuntimeError(f"unknown experiment tools: {', '.join(sorted(unknown))}")
    for name in registered - allowed:
        server.mcp.remove_tool(name)
    server.main()


if __name__ == "__main__":
    main()
