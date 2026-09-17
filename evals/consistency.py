from __future__ import annotations

import statistics
from typing import Any

from evals.metrics import band
from evals.schema import GoldenCase
from jev_mcp.config import AppConfig
from jev_mcp.engine import Engine
from jev_mcp.tools.compare_attempts import run_compare_attempts
from jev_mcp.tools.triage_failure import run_triage_failure

RUNNERS = {
    "compare_attempts": run_compare_attempts,
    "triage_failure": run_triage_failure,
}


async def repeat_case(case: GoldenCase, *, runs: int, data_dir) -> dict[str, Any]:
    config = AppConfig.model_validate(
        {
            "provider": {"name": "typesafe"},
            "data_dir": str(data_dir),
            "cache": {"enabled": False},
        }
    )
    series: dict[str, list[float]] = {}
    for _ in range(runs):
        engine = Engine.create(config)
        try:
            result = await RUNNERS[case.category](engine, **case.input, use_cache=False)
        finally:
            await engine.close()
        for key, value in (result.get("signals") or {}).items():
            series.setdefault(key, []).append(float(value))
    stats = {}
    crossings = {}
    for key, values in series.items():
        stats[key] = {
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "stddev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        }
        labels = [band(value) for value in values]
        crossings[key] = len(set(labels)) > 1
    return {
        "id": case.id,
        "stats": stats,
        "decision_boundary_crossing_rate": (sum(crossings.values()) / len(crossings)) if crossings else 0.0,
        "crossings": crossings,
    }
