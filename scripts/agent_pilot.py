#!/usr/bin/env python3
"""CLI for the paid coding-agent pilot experiment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.experiments.pilot import (  # noqa: E402
    AGENTS,
    CONDITIONS,
    MAX_TOTAL_RUNS,
    PilotOptions,
    build_manifest,
    discover_fixtures,
    execute,
    manifest_json,
    preflight,
    select_values,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the isolated five-task paid-agent pilot (manifest-only by default)."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually invoke paid coding agents; omitted means print the manifest only.",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Check selected binaries, authentication, and the TypeSafe key, then exit.",
    )
    parser.add_argument("--agents", nargs="+", help=f"Agents (choices: {', '.join(AGENTS)}).")
    parser.add_argument(
        "--conditions",
        nargs="+",
        help=f"Conditions (choices: {', '.join(CONDITIONS)}).",
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        help="Fixture names or two-digit prefixes (default: all five).",
    )
    parser.add_argument("--max-runs", type=int, default=MAX_TOTAL_RUNS)
    parser.add_argument("--timeout", type=int, default=600, help="Hard timeout per agent run, seconds.")
    parser.add_argument("--claude-budget", type=float, default=1.0, help="Maximum USD per Claude run.")
    parser.add_argument("--cursor-model", help="Optional Cursor CLI model.")
    parser.add_argument("--out", default="eval-results/agent-pilot")
    parser.add_argument("--seed", type=int, default=7)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        fixtures = discover_fixtures()
        agents = select_values(args.agents, AGENTS, "agent")
        conditions = select_values(args.conditions, tuple(CONDITIONS), "condition")
        fixture_names = [fixture.name for fixture in fixtures]
        tasks = args.tasks or fixture_names
        if args.timeout <= 0:
            raise ValueError("--timeout must be positive")
        if args.claude_budget <= 0:
            raise ValueError("--claude-budget must be positive")
        options = PilotOptions(
            out=Path(args.out).resolve(),
            timeout=args.timeout,
            claude_budget=args.claude_budget,
            cursor_model=args.cursor_model,
            seed=args.seed,
            max_runs=args.max_runs,
        )
        specs = build_manifest(
            fixtures,
            agents,
            conditions,
            tasks,
            max_runs=args.max_runs,
            seed=args.seed,
        )
        if args.preflight:
            result = preflight(agents, conditions)
            print(json.dumps(result, indent=2))
            return 0 if result["ok"] else 2
        if not args.execute:
            print(json.dumps(manifest_json(specs, options), indent=2))
            return 0
        summary = execute(specs, options)
        print(json.dumps(summary, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, indent=2),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
