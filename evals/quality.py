"""Quality if an agent uses Jev. Spec-follow vs blind-follow. Not live Jev IQ."""

from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from evals.runner import RUNNERS, load_cases
from evals.schema import GoldenCase
from evals.scoring import score_case, summarize
from jev_mcp.config import AppConfig
from jev_mcp.engine import Engine
from jev_mcp.models import JudgmentResult
from jev_mcp.providers.mock import MockJudgmentProvider


class NoisyMock(MockJudgmentProvider):
    """Perturb calibrated answers. Tests policy under a sloppy Jev, not a perfect mock."""

    def __init__(self, answers: dict[str, float], *, sigma: float, rng: random.Random) -> None:
        super().__init__(answers=answers, default=0.5)
        self.sigma = sigma
        self.rng = rng

    async def evaluate(self, state: dict, questions) -> JudgmentResult:
        result = await super().evaluate(state, questions)
        noisy = {
            key: min(1.0, max(0.0, value + self.rng.gauss(0.0, self.sigma)))
            for key, value in result.answers.items()
        }
        return result.model_copy(update={"answers": noisy})


async def _run(case: GoldenCase, provider, data_dir: Path) -> dict[str, Any]:
    config = AppConfig.model_validate(
        {
            "provider": {"name": "mock"},
            "data_dir": str(data_dir),
            "cache": {"enabled": False},
            "server": {"shadow_mode": True},
        }
    )
    engine = Engine.create(config, provider=provider)
    try:
        result = await RUNNERS[case.category](engine, **case.input, use_cache=False)
    finally:
        await engine.close()
    return result


def _agent_harm(case: GoldenCase, result: dict[str, Any]) -> dict[str, int]:
    """Count quality failures under two ways of using the same Jev payload."""
    spec = {"missed_requirements": 0, "critical_dropped": 0, "tasks_abandoned": 0}
    blind = {"missed_requirements": 0, "critical_dropped": 0, "tasks_abandoned": 0}
    if "error" in result:
        return {"spec": spec, "blind": blind}

    if case.category == "rank_context" and case.labels.critical_ids:
        candidates = result.get("candidates") or []
        remaining = {row.get("id") for row in candidates}
        high = {row.get("id") for row in candidates if str(row.get("tier", "")).upper() == "HIGH"}
        for cid in case.labels.critical_ids:
            if cid not in remaining:
                spec["critical_dropped"] += 1
            if cid not in high:
                blind["critical_dropped"] += 1

    if case.category == "check_completion":
        review = set(result.get("review_requirements") or [])
        needed = set(case.labels.review_ids)
        spec["missed_requirements"] += len(needed - review)
        if result.get("status") != "INCOMPLETE":
            # Blind ships when Jev did not scream INCOMPLETE — skips the review list.
            blind["missed_requirements"] += len(needed)

    if case.category == "compare_attempts":
        expected = case.labels.expected_status
        status = result.get("status")
        if expected == "PROGRESSING" and status == "LIKELY_STUCK":
            blind["tasks_abandoned"] += 1
        if expected == "LIKELY_STUCK" and status == "PROGRESSING":
            # Spec still lets the frontier keep working; blind treats CONTINUE as "keep same strategy".
            spec["tasks_abandoned"] += 0

    return {"spec": spec, "blind": blind}


def _sum_harm(rows: list[dict[str, Any]], policy: str) -> dict[str, int]:
    totals = {"missed_requirements": 0, "critical_dropped": 0, "tasks_abandoned": 0}
    for row in rows:
        for key in totals:
            totals[key] += row["harm"][policy][key]
    return totals


async def run_quality(*, data_dir: Path, sigma: float = 0.15, seed: int = 7) -> dict[str, Any]:
    cases = load_cases()
    rng = random.Random(seed)
    clean_rows: list[dict[str, Any]] = []
    noisy_rows: list[dict[str, Any]] = []

    for case in cases:
        clean = await _run(case, MockJudgmentProvider(answers=case.mock_answers), data_dir)
        noisy = await _run(
            case,
            NoisyMock(case.mock_answers, sigma=sigma, rng=rng),
            data_dir,
        )
        clean_scored = score_case(case, clean)
        noisy_scored = score_case(case, noisy)
        clean_scored["category"] = case.category
        noisy_scored["category"] = case.category
        clean_scored["uncertain_expected"] = case.labels.uncertain_expected
        noisy_scored["uncertain_expected"] = case.labels.uncertain_expected
        clean_scored["harm"] = _agent_harm(case, clean)
        noisy_scored["harm"] = _agent_harm(case, noisy)
        clean_rows.append(clean_scored)
        noisy_rows.append(noisy_scored)

    by_cat: dict[str, int] = defaultdict(int)
    for case in cases:
        by_cat[case.category] += 1

    return {
        "kind": "quality_if_agent_uses_jev",
        "disclaimer": (
            "Software + policy quality, not hosted Jev intelligence and not a 30-task coding bakeoff. "
            "Clean mock answers are constructed to match labels. Noise (±0.15) asks: if Jev is sloppy, "
            "does spec-follow still avoid the expensive failures?"
        ),
        "n": len(cases),
        "categories": dict(by_cat),
        "sigma": sigma,
        "seed": seed,
        "software_clean": summarize(clean_rows),
        "software_noisy": summarize(noisy_rows),
        "agent_clean": {
            "spec_follow": _sum_harm(clean_rows, "spec"),
            "blind_follow": _sum_harm(clean_rows, "blind"),
        },
        "agent_noisy": {
            "spec_follow": _sum_harm(noisy_rows, "spec"),
            "blind_follow": _sum_harm(noisy_rows, "blind"),
        },
    }
