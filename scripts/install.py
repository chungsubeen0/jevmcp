#!/usr/bin/env python3
"""Print or write local MCP client configuration snippets."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _command() -> list[str]:
    exe = shutil.which("jev-mcp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "jev_mcp"]


def mcp_config() -> dict:
    return {
        "mcpServers": {
            "jev": {
                "command": _command()[0],
                "args": _command()[1:],
                "env": {
                    "TYPESAFE_API_KEY": "${TYPESAFE_API_KEY}",
                    "JEV_MCP_PROFILE": "interactive",
                    "JEV_MCP_SHADOW_MODE": "true",
                },
            }
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit Jev MCP client install snippets")
    parser.add_argument("--client", choices=["codex", "claude-code", "generic"], default="generic")
    parser.add_argument("--write")
    args = parser.parse_args(argv)
    config = mcp_config()
    if args.client == "codex":
        note = REPO / "integrations" / "codex" / "mcp-config.example.json"
        print(f"# See also {note}")
    elif args.client == "claude-code":
        note = REPO / "integrations" / "claude-code" / "mcp-config.example.json"
        print(f"# See also {note}")
    text = json.dumps(config, indent=2)
    if args.write:
        Path(args.write).write_text(text + "\n", encoding="utf-8")
    print(text)
    print("\n# Copy AGENTS.md / CLAUDE.md examples from integrations/ and set TYPESAFE_API_KEY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
