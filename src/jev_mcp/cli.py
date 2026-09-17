"""CLI entry points used by console scripts and scripts/ wrappers."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from jev_mcp import __version__
from jev_mcp.config import load_config
from jev_mcp.engine import Engine
from jev_mcp.models import JudgmentQuestion, OutcomeFeedback
from jev_mcp.providers.mock import MockProvider
from jev_mcp.providers.typesafe import TypeSafeProvider


def doctor_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Jev MCP configuration")
    parser.add_argument("--config")
    parser.add_argument("--ping", action="store_true", help="Make a tiny TypeSafe call")
    args = parser.parse_args(argv)
    config = load_config(config_path=args.config)
    data_dir = config.resolve_data_dir()
    print(f"jev-mcp {__version__}")
    print(f"provider: {config.provider.name}")
    print(f"model: {config.provider.model}")
    print(f"profile: {config.profile.default}")
    print(f"shadow_mode: {config.server.shadow_mode}")
    print(f"api_key_configured: {bool(config.provider.api_key)}")
    print(f"data_dir: {data_dir}")
    print(f"cache_path: {config.cache_path()}")
    print(f"telemetry_path: {config.telemetry_path()}")
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe = data_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print("data_dir_writable: true")
    except OSError as exc:
        print(f"data_dir_writable: false ({exc})")
        return 1

    if not args.ping:
        print("ping: skipped (TypeSafe is not contacted unless --ping)")
        return 0

    if config.provider.name == "mock":
        print("ping: mock provider ready")
        return 0
    if not config.provider.api_key:
        print("ping: failed (TYPESAFE_API_KEY missing)")
        return 1

    async def _ping() -> None:
        provider = TypeSafeProvider(config)
        try:
            result = await provider.evaluate(
                {"probe": "health check"},
                [JudgmentQuestion(id="reachable", question="Is this a health-check probe?")],
            )
            print(f"ping: ok model={result.model} latency_ms={result.latency_ms}")
        finally:
            await provider.close()

    try:
        asyncio.run(_ping())
    except Exception as exc:
        print(f"ping: failed ({exc})")
        return 1
    return 0


def _load_dataset(root: Path) -> list[dict]:
    cases: list[dict] = []
    for path in sorted((root / "dataset").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            cases.extend(payload)
        else:
            cases.append(payload)
    return cases


def _direction(value: float, low: float = 0.30, high: float = 0.70) -> str:
    if value <= low:
        return "LOW"
    if value >= high:
        return "HIGH"
    return "UNCERTAIN"


def _apply_fixture_answers(case: dict) -> MockProvider:
    answers = case.get("mock_answers") or {}
    return MockProvider(answers=answers, default=0.5)


async def _run_benchmark(config, cases: list[dict], provider_name: str) -> dict:
    from jev_mcp.tools.assess_risk import run_assess_risk
    from jev_mcp.tools.check_completion import run_check_completion
    from jev_mcp.tools.classify_findings import run_classify_findings
    from jev_mcp.tools.compare_attempts import run_compare_attempts
    from jev_mcp.tools.judge import run_judge
    from jev_mcp.tools.rank_context import run_rank_context
    from jev_mcp.tools.triage_failure import run_triage_failure

    runners = {
        "jev_triage_failure": run_triage_failure,
        "jev_compare_attempts": run_compare_attempts,
        "jev_check_completion": run_check_completion,
        "jev_rank_context": run_rank_context,
        "jev_classify_findings": run_classify_findings,
        "jev_assess_risk": run_assess_risk,
        "jev_judge": run_judge,
    }
    latencies: list[int] = []
    directional_hits = 0
    directional_total = 0
    uncertain_cases = 0
    false_pos = 0
    false_neg = 0
    cost = 0.0
    for case in cases:
        tool = case["tool"]
        runner = runners[tool]
        if provider_name == "mock":
            engine = Engine.create(config, provider=_apply_fixture_answers(case))
        else:
            engine = Engine.create(config)
        try:
            result = await runner(engine, **case["input"], use_cache=False)
        finally:
            await engine.close()
        if "error" in result:
            continue
        latency = int(result.get("meta", {}).get("latency_ms") or 0)
        latencies.append(latency)
        if result.get("meta", {}).get("jev_estimated_cost"):
            cost += float(result["meta"]["jev_estimated_cost"])
        expected = case.get("expected") or {}
        signals = result.get("signals") or result.get("answers") or {}
        if expected.get("uncertain_expected"):
            uncertain_cases += 1
        for key, spec in (expected.get("signals") or {}).items():
            if key not in signals:
                continue
            actual = float(signals[key])
            direction = spec.get("direction")
            minimum = spec.get("min")
            maximum = spec.get("max")
            directional_total += 1
            ok = True
            if direction and _direction(actual) != direction:
                ok = False
            if minimum is not None and actual < minimum:
                ok = False
            if maximum is not None and actual > maximum:
                ok = False
            if ok:
                directional_hits += 1
            elif direction == "HIGH":
                false_neg += 1
            elif direction == "LOW":
                false_pos += 1
    latencies.sort()

    def pct(p: float) -> int:
        if not latencies:
            return 0
        index = min(len(latencies) - 1, int(round((p / 100) * (len(latencies) - 1))))
        return latencies[index]

    return {
        "dataset_size": len(cases),
        "provider": provider_name,
        "model": config.provider.model if provider_name != "mock" else "mock-jev",
        "latency_p50": pct(50),
        "latency_p95": pct(95),
        "cache_disabled": True,
        "directional_accuracy": (directional_hits / directional_total) if directional_total else None,
        "uncertain_cases": uncertain_cases,
        "false_positive_rate": (false_pos / directional_total) if directional_total else None,
        "false_negative_rate": (false_neg / directional_total) if directional_total else None,
        "estimated_provider_cost": cost,
    }


def benchmark_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local Jev MCP benchmark corpus")
    parser.add_argument("--config")
    parser.add_argument("--provider", choices=["mock", "typesafe"], default="mock")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[2] / "benchmarks"),
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    cases = _load_dataset(root)
    overrides = {"provider": {"name": args.provider}, "cache": {"enabled": False}}
    config = load_config(config_path=args.config, cli_overrides=overrides)
    summary = asyncio.run(_run_benchmark(config, cases, args.provider))
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def export_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export local Jev MCP telemetry")
    parser.add_argument("--config")
    parser.add_argument("--output")
    parser.add_argument("--record-outcome", help="JSON OutcomeFeedback to attach")
    args = parser.parse_args(argv)
    config = load_config(config_path=args.config)

    async def _export() -> list[dict]:
        engine = Engine.create(config)
        try:
            if args.record_outcome:
                payload = json.loads(Path(args.record_outcome).read_text(encoding="utf-8"))
                await engine.telemetry.record_outcome(OutcomeFeedback.model_validate(payload))
            return engine.telemetry.export_rows()
        finally:
            await engine.close()

    rows = asyncio.run(_export())
    text = json.dumps(rows, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0
