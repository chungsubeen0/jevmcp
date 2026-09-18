from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest
from evals.experiments.pilot import (
    CONDITIONS,
    MAX_TOTAL_RUNS,
    PilotOptions,
    ProcessResult,
    RunSpec,
    agent_environment,
    aggregate,
    build_agent_command,
    build_manifest,
    combine_run_success,
    discover_fixtures,
    parse_agent_metrics,
    prepare_workspace,
    score_workspace,
)
from evals.experiments.report import compare_to_baseline


def _spec(agent: str, condition: str) -> RunSpec:
    return RunSpec(agent=agent, condition=condition, fixture=discover_fixtures()[0])


def test_prepare_workspace_copies_public_only_and_resets_attempts(tmp_path: Path):
    spec = _spec("claude", "B_triage")
    _, first, _ = prepare_workspace(spec, tmp_path, 1, 0)
    assert not (first / "hidden").exists()
    assert not (first / "hidden_tests").exists()
    assert (first / ".git").is_dir()
    (first / "invoice_math" / "rounding.py").write_text("# changed\n", encoding="utf-8")

    _, second, _ = prepare_workspace(spec, tmp_path, 1, 1)
    assert "# changed" not in (second / "invoice_math" / "rounding.py").read_text(encoding="utf-8")
    assert not (second / "hidden_tests").exists()


def test_hidden_tests_are_injected_only_during_scoring(tmp_path: Path):
    spec = _spec("claude", "A_frontier_only")
    run_dir, workspace, _ = prepare_workspace(spec, tmp_path, 1, 0)
    assert not (workspace / "hidden_tests").exists()

    score = score_workspace(spec, workspace, run_dir, timeout=30)

    assert (workspace / "hidden_tests").is_dir()
    assert score["success"] is False
    assert score["regression"] is False


def test_condition_tools_are_filtered_for_claude_and_codex(tmp_path: Path):
    options = PilotOptions(out=tmp_path)
    for agent in ("claude", "codex"):
        spec = _spec(agent, "B_triage")
        run_dir, workspace, config = prepare_workspace(spec, tmp_path, 1, 0)
        command = " ".join(build_agent_command(spec, workspace, config, options))
        assert "jev_triage_failure" in command
        assert "jev_compare_attempts" not in command
        assert str(run_dir) in command
        if agent == "claude":
            assert "stream-json" in command

        baseline = _spec(agent, "A_frontier_only")
        _, baseline_workspace, baseline_config = prepare_workspace(baseline, tmp_path, 2, 0)
        baseline_command = " ".join(
            build_agent_command(baseline, baseline_workspace, baseline_config, options)
        )
        assert "jev_triage_failure" not in baseline_command


def test_metric_parser_handles_json_and_jsonl_without_inventing_values(tmp_path: Path):
    output = tmp_path / "agent.jsonl"
    output.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "call-1",
                                    "name": "mcp__jev__jev_triage_failure",
                                }
                            ]
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "result",
                        "usage": {
                            "input_tokens": 100,
                            "output_tokens": 20,
                            "cache_read_input_tokens": 30,
                        },
                        "total_cost_usd": 0.01,
                        "num_turns": 1,
                    }
                ),
            )
        ),
        encoding="utf-8",
    )

    metrics = parse_agent_metrics(output)

    assert metrics.input_tokens == 100
    assert metrics.output_tokens == 20
    assert metrics.cache_tokens == 30
    assert metrics.total_tokens == 150
    assert metrics.reported_cost_usd == pytest.approx(0.01)
    assert metrics.jev_calls == {"jev_triage_failure": 1}
    assert metrics.human_escalations == 0

    empty = tmp_path / "empty"
    empty.write_text("not json\n", encoding="utf-8")
    unavailable = parse_agent_metrics(empty)
    assert unavailable.total_tokens is None
    assert unavailable.reported_cost_usd is None
    assert unavailable.human_escalations is None

    codex = tmp_path / "codex.jsonl"
    codex.write_text(
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 80,
                    "output_tokens": 20,
                },
            }
        ),
        encoding="utf-8",
    )
    codex_metrics = parse_agent_metrics(codex)
    assert codex_metrics.cache_tokens == 80
    assert codex_metrics.total_tokens == 120

    cursor = tmp_path / "cursor.jsonl"
    cursor.write_text(
        "\n".join(
            (
                json.dumps(
                    {
                        "type": "tool_call",
                        "subtype": "started",
                        "call_id": "cursor-call-1",
                        "tool_call": {
                            "mcpToolCall": {
                                "args": {
                                    "name": "jev-jev_check_completion",
                                    "toolCallId": "cursor-call-1",
                                }
                            }
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "tool_call",
                        "subtype": "completed",
                        "call_id": "cursor-call-1",
                        "tool_call": {
                            "mcpToolCall": {
                                "args": {
                                    "name": "jev-jev_check_completion",
                                    "toolCallId": "cursor-call-1",
                                }
                            }
                        },
                    }
                ),
            )
        ),
        encoding="utf-8",
    )
    assert parse_agent_metrics(cursor).jev_calls == {"jev_check_completion": 1}


def test_manifest_enforces_hard_run_cap():
    fixtures = discover_fixtures()
    with pytest.raises(ValueError, match="between 1 and"):
        build_manifest(
            fixtures,
            ["claude", "codex", "cursor"],
            list(CONDITIONS),
            [fixture.name for fixture in fixtures],
            max_runs=MAX_TOTAL_RUNS + 1,
            seed=7,
        )


def test_infrastructure_failure_cannot_count_as_success():
    failed = ProcessResult(
        infrastructure_status="process_error",
        returncode=1,
        timed_out=False,
        duration_seconds=0,
        stdout_path="stdout",
        stderr_path="stderr",
    )
    assert combine_run_success(failed, {"success": True}) is False


def test_agent_environment_does_not_forward_unrelated_secrets(monkeypatch):
    monkeypatch.setenv("UNRELATED_SECRET", "do-not-forward")
    monkeypatch.setenv("TYPESAFE_API_KEY", "needed-for-mcp")

    baseline = agent_environment(_spec("claude", "A_frontier_only"))
    jev = agent_environment(_spec("claude", "B_triage"))

    assert "UNRELATED_SECRET" not in baseline
    assert "TYPESAFE_API_KEY" not in baseline
    assert jev["TYPESAFE_API_KEY"] == "needed-for-mcp"


def test_aggregate_preserves_unavailable_cost_and_tokens():
    metrics = {
        "input_tokens": None,
        "output_tokens": None,
        "cache_tokens": None,
        "total_tokens": None,
        "reported_cost_usd": None,
        "tool_calls": {},
        "jev_calls": {},
        "iterations": None,
        "human_escalations": None,
    }
    rows = [
        {
            "agent": "cursor",
            "condition": "A_frontier_only",
            "success": True,
            "duration_seconds": 1.0,
            "metrics": metrics,
        }
    ]

    summary = aggregate(rows, seed=7)[0]

    assert summary["success_rate"] == 1.0
    assert summary["total_tokens"] is None
    assert summary["reported_cost_usd"] is None
    assert summary["tokens_per_successful_task"] is None
    assert summary["cost_per_successful_task_usd"] is None
    assert asdict(parse_agent_metrics(Path("/dev/null")))["total_tokens"] is None


def test_report_prefers_cost_and_rejects_quality_tradeoff():
    groups = [
        {
            "agent": "claude",
            "condition": "A_frontier_only",
            "success_rate": 1.0,
            "tokens_per_successful_task": 100.0,
            "cost_per_successful_task_usd": 1.0,
            "human_escalations": 2,
        },
        {
            "agent": "claude",
            "condition": "B_triage",
            "success_rate": 1.0,
            "tokens_per_successful_task": 90.0,
            "cost_per_successful_task_usd": 0.8,
            "human_escalations": 1,
        },
        {
            "agent": "claude",
            "condition": "C_triage_and_stuck",
            "success_rate": 0.8,
            "tokens_per_successful_task": 70.0,
            "cost_per_successful_task_usd": 0.7,
            "human_escalations": 1,
        },
    ]

    comparisons = {row["condition"]: row for row in compare_to_baseline(groups)}

    assert comparisons["B_triage"]["verdict"] == "promising"
    assert comparisons["B_triage"]["cost_per_successful_task_delta_percent"] == pytest.approx(-20)
    assert comparisons["C_triage_and_stuck"]["verdict"] == "quality_tradeoff"
