"""Combined descriptive report for completed agent-pilot runs."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from evals.experiments.pilot import aggregate, parse_agent_metrics


def load_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                attempts = row.get("attempt_logs") or []
                if attempts:
                    stdout = Path(attempts[-1]["process"]["stdout_path"])
                    if stdout.is_file():
                        row["metrics"] = asdict(parse_agent_metrics(stdout))
                rows.append(row)
    return rows


def _delta_percent(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline in (None, 0):
        return None
    return 100.0 * (value - baseline) / baseline


def compare_to_baseline(groups: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_agent: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for group in groups:
        by_agent[str(group["agent"])][str(group["condition"])] = group
    comparisons: list[dict[str, Any]] = []
    for agent, conditions in sorted(by_agent.items()):
        baseline = conditions.get("A_frontier_only")
        if baseline is None:
            continue
        for condition, current in sorted(conditions.items()):
            if condition == "A_frontier_only":
                continue
            token_delta = _delta_percent(
                current.get("tokens_per_successful_task"),
                baseline.get("tokens_per_successful_task"),
            )
            cost_delta = _delta_percent(
                current.get("cost_per_successful_task_usd"),
                baseline.get("cost_per_successful_task_usd"),
            )
            success_delta = float(current["success_rate"]) - float(baseline["success_rate"])
            primary_delta = cost_delta if cost_delta is not None else token_delta
            if primary_delta is None:
                verdict = "insufficient_economic_telemetry"
            elif success_delta < 0:
                verdict = "quality_tradeoff"
            elif primary_delta < 0:
                verdict = "promising"
            else:
                verdict = "no_savings_observed"
            comparisons.append(
                {
                    "agent": agent,
                    "condition": condition,
                    "success_rate_delta": success_delta,
                    "tokens_per_successful_task_delta_percent": token_delta,
                    "cost_per_successful_task_delta_percent": cost_delta,
                    "human_escalation_delta": (
                        current["human_escalations"] - baseline["human_escalations"]
                        if current.get("human_escalations") is not None
                        and baseline.get("human_escalations") is not None
                        else None
                    ),
                    "verdict": verdict,
                }
            )
    return comparisons


def build_report(rows: list[dict[str, Any]], *, seed: int = 7) -> dict[str, Any]:
    groups = aggregate(rows, seed)
    agents = sorted({str(row["agent"]) for row in rows})
    return {
        "kind": "agent_pilot_combined_report",
        "run_count": len(rows),
        "agents": agents,
        "aggregates": groups,
        "comparisons_to_frontier_only": compare_to_baseline(groups),
        "limitations": [
            "Five tasks per condition provide descriptive pilot evidence, not statistical proof.",
            "Codex and Cursor may not report dollar cost; token comparisons remain within agent.",
            "Cursor CLI stream does not expose token or cost telemetry.",
            "Human escalation counts detect explicit tool events only.",
            "Jev cost is unavailable when provider pricing is not configured.",
        ],
    }
