from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from evals.schema import GoldenCase
from evals.scoring import score_case, summarize
from jev_mcp.config import AppConfig
from jev_mcp.engine import Engine
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.assess_risk import run_assess_risk
from jev_mcp.tools.check_completion import run_check_completion
from jev_mcp.tools.classify_findings import run_classify_findings
from jev_mcp.tools.compare_attempts import run_compare_attempts
from jev_mcp.tools.rank_context import run_rank_context
from jev_mcp.tools.triage_failure import run_triage_failure

RUNNERS = {
    "compare_attempts": run_compare_attempts,
    "triage_failure": run_triage_failure,
    "check_completion": run_check_completion,
    "rank_context": run_rank_context,
    "classify_findings": run_classify_findings,
    "assess_risk": run_assess_risk,
}

GOLDEN = Path(__file__).parent / "golden"


def load_cases(root: Path | None = None) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    for path in sorted((root or GOLDEN).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                cases.append(GoldenCase.model_validate(json.loads(line)))
    return cases


async def run_case(case: GoldenCase, *, live: bool, data_dir: Path) -> dict[str, Any]:
    config = AppConfig.model_validate(
        {
            "provider": {"name": "typesafe" if live else "mock"},
            "data_dir": str(data_dir),
            "cache": {"enabled": False},
        }
    )
    provider = None if live else MockJudgmentProvider(answers=case.mock_answers)
    engine = Engine.create(config, provider=provider)
    try:
        result = await RUNNERS[case.category](engine, **case.input, use_cache=False)
    finally:
        await engine.close()
    scored = score_case(case, result)
    scored["category"] = case.category
    scored["uncertain_expected"] = case.labels.uncertain_expected
    keep = ("status", "signals", "requirements", "candidates")
    scored["result"] = {key: result.get(key) for key in keep if key in result}
    return scored


async def run_suite(cases: Iterable[GoldenCase], *, live: bool, data_dir: Path) -> dict[str, Any]:
    rows = [await run_case(case, live=live, data_dir=data_dir) for case in cases]
    summary = summarize(rows)
    summary["rows"] = rows
    return summary
