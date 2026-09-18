"""Level B/C frontier-context proxies. Not exact token savings."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from jev_mcp.config import AppConfig
from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockProvider
from jev_mcp.tools.assess_risk import run_assess_risk
from jev_mcp.tools.check_completion import run_check_completion
from jev_mcp.tools.classify_findings import run_classify_findings
from jev_mcp.tools.compare_attempts import run_compare_attempts
from jev_mcp.tools.judge import run_judge
from jev_mcp.tools.rank_context import run_rank_context
from jev_mcp.tools.triage_failure import run_triage_failure

CHARS_PER_TOKEN = 4.0
ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmarks" / "dataset"

CONFIGS: dict[str, list[str]] = {
    "A_frontier_only": [],
    "B_triage": ["jev_triage_failure"],
    "C_triage_and_stuck": ["jev_triage_failure", "jev_compare_attempts"],
    "D_all": [
        "jev_triage_failure",
        "jev_compare_attempts",
        "jev_check_completion",
        "jev_rank_context",
        "jev_classify_findings",
        "jev_assess_risk",
        "jev_judge",
    ],
}

RUNNERS = {
    "jev_triage_failure": run_triage_failure,
    "jev_compare_attempts": run_compare_attempts,
    "jev_check_completion": run_check_completion,
    "jev_rank_context": run_rank_context,
    "jev_classify_findings": run_classify_findings,
    "jev_assess_risk": run_assess_risk,
    "jev_judge": run_judge,
}


def _json_chars(value: Any) -> int:
    return len(json.dumps(value, default=str, separators=(",", ":")))


def load_benchmark_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(BENCHMARK.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else [payload]
        for row in rows:
            row = dict(row)
            row["source"] = "benchmark"
            cases.append(row)
    return cases


def scale_probes() -> list[dict[str, Any]]:
    """Same local-triage fixture, growing test logs. Mechanism, not production savings."""
    base = json.loads((BENCHMARK / "failure_triage.json").read_text(encoding="utf-8"))[0]
    probes = []
    for size in (2_000, 8_000, 32_000, 80_000):
        case = json.loads(json.dumps(base))
        line = "FAIL src/webhooks/stripe.test.ts guest_identity expected UUID got null\n"
        case["id"] = f"scale-triage-{size}"
        case["source"] = "scale_probe"
        case["input"]["failure"]["output"] = (line * ((size // len(line)) + 1))[:size]
        probes.append(case)
    return probes


def compact_payload(result: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "status",
        "signals",
        "answers",
        "classification",
        "control_signal",
        "requirements",
        "candidates",
        "findings",
        "review_requirements",
    )
    return {key: result[key] for key in keep if key in result}


def level_c(result: dict[str, Any]) -> dict[str, int]:
    stuck = 1 if result.get("status") == "LIKELY_STUCK" else 0
    low_tier = 0
    for candidate in result.get("candidates") or []:
        if str(candidate.get("tier") or "").upper() == "LOW":
            low_tier += 1
    gaps = len(result.get("review_requirements") or [])
    return {
        "stuck_loops_detected": stuck,
        "candidates_deprioritized": low_tier,
        "requirements_isolated": gaps,
    }


def measure_case(case: dict[str, Any], result: dict[str, Any] | None) -> dict[str, Any]:
    evidence = _json_chars(case["input"])
    compact = _json_chars(compact_payload(result)) if result and "error" not in result else 0
    avoided = max(0, evidence - compact) if result and "error" not in result else 0
    extras = level_c(result) if result and "error" not in result else {
        "stuck_loops_detected": 0,
        "candidates_deprioritized": 0,
        "requirements_isolated": 0,
    }
    return {
        "id": case["id"],
        "tool": case["tool"],
        "source": case.get("source", "benchmark"),
        "evidence_chars": evidence,
        "compact_chars": compact,
        "context_avoided_chars": avoided,
        "frontier_tokens_if_reread_estimate": round(evidence / CHARS_PER_TOKEN),
        "compact_tokens_estimate": round(compact / CHARS_PER_TOKEN),
        "context_avoided_tokens_estimate": round(avoided / CHARS_PER_TOKEN),
        **extras,
        "error": (result or {}).get("error"),
    }


async def run_case(case: dict[str, Any], *, live: bool, data_dir: Path) -> dict[str, Any]:
    config = AppConfig.model_validate(
        {
            "provider": {"name": "typesafe" if live else "mock"},
            "data_dir": str(data_dir),
            "cache": {"enabled": False},
            "server": {"shadow_mode": True},
        }
    )
    provider = None if live else MockProvider(answers=case.get("mock_answers") or {}, default=0.5)
    engine = Engine.create(config, provider=provider)
    try:
        result = await RUNNERS[case["tool"]](engine, **case["input"], use_cache=False)
    finally:
        await engine.close()
    return result


def summarize(rows: list[dict[str, Any]], *, tools: list[str], label: str) -> dict[str, Any]:
    selected = [row for row in rows if not tools or row["tool"] in tools]
    if label == "A_frontier_only":
        selected = [
            {
                **row,
                "compact_chars": 0,
                "context_avoided_chars": 0,
                "compact_tokens_estimate": 0,
                "context_avoided_tokens_estimate": 0,
                "stuck_loops_detected": 0,
                "candidates_deprioritized": 0,
                "requirements_isolated": 0,
            }
            for row in selected
        ]
    n = len(selected)
    evidence = sum(row["evidence_chars"] for row in selected)
    avoided = sum(row["context_avoided_chars"] for row in selected)
    return {
        "config": label,
        "tools": tools,
        "n": n,
        "jev_calls": 0 if label == "A_frontier_only" else n,
        "evidence_chars": evidence,
        "context_avoided_chars": avoided,
        "frontier_tokens_if_reread_estimate": round(evidence / CHARS_PER_TOKEN),
        "context_avoided_tokens_estimate": round(avoided / CHARS_PER_TOKEN),
        "share_of_evidence_kept_out_of_frontier": (avoided / evidence) if evidence else 0.0,
        "stuck_loops_detected": sum(row["stuck_loops_detected"] for row in selected),
        "candidates_deprioritized": sum(row["candidates_deprioritized"] for row in selected),
        "requirements_isolated": sum(row["requirements_isolated"] for row in selected),
    }


async def run_savings(*, live: bool, data_dir: Path) -> dict[str, Any]:
    cases = load_benchmark_cases() + scale_probes()
    measured: list[dict[str, Any]] = []
    for case in cases:
        result = await run_case(case, live=live, data_dir=data_dir)
        measured.append(measure_case(case, result))

    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in measured:
        by_source[row["source"]].append(row)

    configs = {name: summarize(by_source["benchmark"], tools=tools, label=name) for name, tools in CONFIGS.items()}
    scale = [row for row in measured if row["source"] == "scale_probe"]
    return {
        "kind": "level_b_c_proxy",
        "disclaimer": (
            "Level B/C estimates only. Assumes 4 characters per token and that the frontier "
            "would otherwise reread the same evidence to classify it. Not exact frontier token savings."
        ),
        "chars_per_token": CHARS_PER_TOKEN,
        "provider": "typesafe" if live else "mock",
        "configs": configs,
        "by_tool": _by_tool(by_source["benchmark"]),
        "scale_probes": scale,
        "rows": [row for row in measured if row["source"] == "benchmark"],
    }


def _by_tool(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["tool"]].append(row)
    out = {}
    for tool, items in sorted(groups.items()):
        evidence = sum(item["evidence_chars"] for item in items)
        avoided = sum(item["context_avoided_chars"] for item in items)
        out[tool] = {
            "n": len(items),
            "evidence_chars": evidence,
            "context_avoided_chars": avoided,
            "context_avoided_tokens_estimate": round(avoided / CHARS_PER_TOKEN),
            "share_kept_out": (avoided / evidence) if evidence else 0.0,
        }
    return out
