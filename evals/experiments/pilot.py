"""Reproducible paid-agent pilot harness for the five bundled coding tasks.

The module itself is dependency-free.  It deliberately treats agent execution
failures separately from task failures and never exposes scorer-only tests
until the agent process has exited.
"""

from __future__ import annotations

import json
import math
import os
import random
import shutil
import signal
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "pilot_tasks"
ALL_JEV_TOOLS = (
    "jev_triage_failure",
    "jev_compare_attempts",
    "jev_check_completion",
    "jev_rank_context",
    "jev_classify_findings",
    "jev_assess_risk",
    "jev_judge",
)
CONDITIONS: dict[str, tuple[str, ...]] = {
    "A_frontier_only": (),
    "B_triage": ("jev_triage_failure",),
    "C_triage_and_stuck": ("jev_triage_failure", "jev_compare_attempts"),
    "D_all": ALL_JEV_TOOLS,
}
AGENTS = ("claude", "codex", "cursor")
MAX_TOTAL_RUNS = 60


@dataclass(frozen=True)
class Fixture:
    name: str
    root: Path
    public: Path
    hidden: Path
    task_text: str
    initial_visible_pass: bool


@dataclass(frozen=True)
class RunSpec:
    agent: str
    condition: str
    fixture: Fixture

    @property
    def tools(self) -> tuple[str, ...]:
        return CONDITIONS[self.condition]


@dataclass(frozen=True)
class PilotOptions:
    out: Path
    timeout: int = 600
    claude_budget: float = 1.0
    cursor_model: str | None = None
    seed: int = 7
    max_runs: int = MAX_TOTAL_RUNS


@dataclass
class ProcessResult:
    infrastructure_status: str
    returncode: int | None
    timed_out: bool
    duration_seconds: float
    stdout_path: str
    stderr_path: str


@dataclass
class TestResult:
    passed: bool
    returncode: int | None
    duration_seconds: float
    stdout_path: str
    stderr_path: str


@dataclass
class ParsedMetrics:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_tokens: int | None = None
    total_tokens: int | None = None
    reported_cost_usd: float | None = None
    tool_calls: dict[str, int] = field(default_factory=dict)
    jev_calls: dict[str, int] = field(default_factory=dict)
    iterations: int | None = None
    human_escalations: int | None = None


def discover_fixtures(base: Path = FIXTURES) -> list[Fixture]:
    """Find and validate exactly the five numbered pilot fixtures."""
    roots = sorted(path for path in base.iterdir() if path.is_dir() and path.name[:2].isdigit())
    if len(roots) != 5:
        raise ValueError(f"expected five pilot fixtures under {base}, found {len(roots)}")
    fixtures: list[Fixture] = []
    for root in roots:
        public = root / "public"
        hidden = root / "hidden"
        task = public / "TASK.md"
        metadata = root / "fixture.json"
        if not task.is_file():
            raise ValueError(f"fixture is missing public/TASK.md: {root}")
        if not hidden.is_dir() or not any(hidden.glob("test_*.py")):
            raise ValueError(f"fixture has no hidden tests: {root}")
        if not metadata.is_file():
            raise ValueError(f"fixture is missing fixture.json: {root}")
        fixture_metadata = json.loads(metadata.read_text(encoding="utf-8"))
        initial_visible_pass = fixture_metadata.get("initial_visible_pass")
        if not isinstance(initial_visible_pass, bool):
            raise ValueError(f"fixture initial_visible_pass must be boolean: {root}")
        fixtures.append(
            Fixture(
                name=root.name,
                root=root,
                public=public,
                hidden=hidden,
                task_text=task.read_text(encoding="utf-8"),
                initial_visible_pass=initial_visible_pass,
            )
        )
    return fixtures


def select_values(raw: Sequence[str] | None, allowed: Sequence[str], label: str) -> list[str]:
    if not raw:
        return list(allowed)
    values = [part for item in raw for part in item.split(",") if part]
    unknown = sorted(set(values) - set(allowed))
    if unknown:
        raise ValueError(f"unknown {label}: {', '.join(unknown)}")
    return values


def build_manifest(
    fixtures: Sequence[Fixture],
    agents: Sequence[str],
    conditions: Sequence[str],
    tasks: Sequence[str],
    *,
    max_runs: int,
    seed: int,
) -> list[RunSpec]:
    if not 1 <= max_runs <= MAX_TOTAL_RUNS:
        raise ValueError(f"--max-runs must be between 1 and {MAX_TOTAL_RUNS}")
    by_name = {fixture.name: fixture for fixture in fixtures}
    aliases = {fixture.name[:2]: fixture.name for fixture in fixtures}
    selected_names: list[str] = []
    for task in tasks:
        name = aliases.get(task, task)
        if name not in by_name:
            raise ValueError(f"unknown task: {task}")
        selected_names.append(name)
    specs = [
        RunSpec(agent=agent, condition=condition, fixture=by_name[task])
        for agent in agents
        for condition in conditions
        for task in selected_names
    ]
    random.Random(seed).shuffle(specs)
    return specs[:max_runs]


def manifest_json(specs: Sequence[RunSpec], options: PilotOptions) -> dict[str, Any]:
    return {
        "execute": False,
        "run_count": len(specs),
        "max_total_runs": MAX_TOTAL_RUNS,
        "timeout_seconds": options.timeout,
        "claude_budget_usd": options.claude_budget,
        "cursor_model": options.cursor_model,
        "seed": options.seed,
        "runs": [
            {
                "agent": spec.agent,
                "condition": spec.condition,
                "task": spec.fixture.name,
                "tools": list(spec.tools),
            }
            for spec in specs
        ],
    }


def condition_policy(condition: str) -> str:
    tools = CONDITIONS[condition]
    if not tools:
        return "Condition policy: No Jev MCP tools are available. Solve the task using normal coding tools only."
    names = ", ".join(tools)
    rules = [
        f"Condition policy: Only these Jev tools may be used: {names}. "
        "Do not call any other Jev tool. Jev probabilities are evidence, never authority; "
        "verify conclusions against the repository and tests. "
        "Keep the stated goal fixed and pass use_cache=false on every Jev call.",
        "After the first non-trivial failing test, lint, typecheck, or build with unclear scope, "
        "call jev_triage_failure before broad investigation. Never skip a failing check.",
    ]
    if "jev_compare_attempts" in tools:
        rules.append(
            "After two materially unsuccessful attempts against the same problem, call "
            "jev_compare_attempts before choosing another strategy."
        )
    if condition == "D_all":
        rules.extend(
            (
                "When discovery presents many plausible files, call jev_rank_context and inspect "
                "HIGH first without deleting other candidates.",
                "Before declaring work complete, call jev_check_completion with every explicit "
                "TASK.md requirement and current verification evidence.",
                "For authentication, authorization, secrets, payments, destructive behavior, or "
                "other sensitive changes, call jev_assess_risk before finalizing.",
                "Use jev_classify_findings only for a large finding pile. Use jev_judge only for "
                "one bounded evidence-grounded yes/no proposition, never code or planning.",
            )
        )
    return "\n".join(rules)


def build_prompt(spec: RunSpec) -> str:
    return (
        "Work only inside the current disposable workspace. Implement the task, inspect files, "
        "and run the visible tests. Start by running the visible tests before inspecting the "
        "implementation. Do not ask for confirmation unless a genuinely missing user "
        "decision makes progress impossible.\n\n"
        f"{condition_policy(spec.condition)}\n\n"
        "TASK.md follows exactly:\n\n"
        f"{spec.fixture.task_text}"
    )


def _yaml_string(value: str) -> str:
    return json.dumps(value)


def write_jev_config(run_dir: Path) -> Path:
    data_dir = run_dir / "jev-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config = run_dir / "jev-mcp.yaml"
    config.write_text(
        "\n".join(
            (
                "server:",
                "  shadow_mode: true",
                "provider:",
                "  name: typesafe",
                "profile:",
                "  default: autonomous",
                "cache:",
                "  enabled: false",
                "telemetry:",
                "  enabled: true",
                "  store_content: false",
                "  store_hashes: true",
                "  local_only: true",
                f"  path: {_yaml_string(str(data_dir / 'telemetry.sqlite'))}",
                f"data_dir: {_yaml_string(str(data_dir))}",
                "",
            )
        ),
        encoding="utf-8",
    )
    return config


def mcp_server_json(config: Path, tools: Sequence[str]) -> dict[str, Any]:
    pythonpath = os.pathsep.join((str(ROOT / "src"), str(ROOT)))
    existing = os.environ.get("PYTHONPATH")
    if existing:
        pythonpath = os.pathsep.join((pythonpath, existing))
    data_dir = config.parent / "jev-data"
    return {
        "command": sys.executable,
        "args": ["-m", "evals.experiments.filtered_server", "--config", str(config)],
        "env": {
            "PYTHONPATH": pythonpath,
            "JEV_MCP_DATA_DIR": str(data_dir),
            "JEV_MCP_EXPERIMENT_TOOLS": ",".join(tools),
            "JEV_MCP_PROFILE": "autonomous",
            "JEV_MCP_PROVIDER": "typesafe",
            "JEV_MCP_SHADOW_MODE": "true",
        },
    }


def prepare_workspace(spec: RunSpec, out: Path, sequence: int, retry: int) -> tuple[Path, Path, Path | None]:
    token = uuid.uuid4().hex[:10]
    run_dir = out / "workspaces" / f"{sequence:03d}-{spec.agent}-{spec.condition}-{spec.fixture.name}-r{retry}-{token}"
    workspace = run_dir / "workspace"
    workspace.mkdir(parents=True)
    shutil.copytree(spec.fixture.public, workspace, dirs_exist_ok=True)
    if (workspace / "hidden").exists() or (workspace / "hidden_tests").exists():
        raise RuntimeError("public fixture unexpectedly contains hidden tests")
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Jev Pilot",
            "-c",
            "user.email=pilot@invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "fixture baseline",
        ],
        cwd=workspace,
        check=True,
    )
    config = write_jev_config(run_dir) if spec.tools else None
    return run_dir, workspace, config


def _claude_command(spec: RunSpec, workspace: Path, config: Path | None, options: PilotOptions) -> list[str]:
    normal_tools = ("Read", "Write", "Edit", "Glob", "Grep", "Bash")
    allowed = list(normal_tools) + [f"mcp__jev__{name}" for name in spec.tools]
    command = [
        "claude",
        "-p",
        build_prompt(spec),
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--setting-sources",
        "project",
        "--strict-mcp-config",
        "--dangerously-skip-permissions",
        "--max-budget-usd",
        str(options.claude_budget),
        "--tools",
        ",".join(allowed),
        "--allowedTools",
        ",".join(allowed),
        "--add-dir",
        str(workspace),
    ]
    if config is not None:
        payload = {"mcpServers": {"jev": mcp_server_json(config, spec.tools)}}
        command.extend(("--mcp-config", json.dumps(payload, separators=(",", ":"))))
    else:
        command.extend(("--mcp-config", json.dumps({"mcpServers": {}})))
    return command


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_array(values: Iterable[str]) -> str:
    return "[" + ",".join(_toml_string(value) for value in values) + "]"


def _codex_command(spec: RunSpec, workspace: Path, config: Path | None, _options: PilotOptions) -> list[str]:
    command = [
        "codex",
        "exec",
        "--json",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(workspace),
        "--skip-git-repo-check",
        "-c",
        'approval_policy="never"',
    ]
    if config is not None:
        server = mcp_server_json(config, spec.tools)
        command.extend(
            (
                "-c",
                f"mcp_servers.jev.command={_toml_string(server['command'])}",
                "-c",
                f"mcp_servers.jev.args={_toml_array(server['args'])}",
                "-c",
                "mcp_servers.jev.env="
                + "{"
                + ",".join(f"{key}={_toml_string(value)}" for key, value in server["env"].items())
                + "}",
                "-c",
                f"mcp_servers.jev.enabled_tools={_toml_array(spec.tools)}",
                "-c",
                'mcp_servers.jev.default_tools_approval_mode="approve"',
            )
        )
    command.append(build_prompt(spec))
    return command


def _cursor_command(spec: RunSpec, workspace: Path, config: Path | None, options: PilotOptions) -> list[str]:
    if config is not None:
        cursor_dir = workspace / ".cursor"
        cursor_dir.mkdir()
        (cursor_dir / "mcp.json").write_text(
            json.dumps({"mcpServers": {"jev": mcp_server_json(config, spec.tools)}}, indent=2) + "\n",
            encoding="utf-8",
        )
    command = [
        "cursor-agent",
        "--print",
        "--output-format",
        "stream-json",
        "--workspace",
        str(workspace),
        "--trust",
        "--sandbox",
        "enabled",
        "--force",
    ]
    if config is not None:
        command.append("--approve-mcps")
    if options.cursor_model:
        command.extend(("--model", options.cursor_model))
    command.append(build_prompt(spec))
    return command


def build_agent_command(
    spec: RunSpec, workspace: Path, config: Path | None, options: PilotOptions
) -> list[str]:
    builders = {"claude": _claude_command, "codex": _codex_command, "cursor": _cursor_command}
    return builders[spec.agent](spec, workspace, config, options)


def agent_environment(spec: RunSpec) -> dict[str, str]:
    """Pass runtime essentials and selected credentials, not arbitrary parent secrets."""
    names = {
        "HOME",
        "LANG",
        "LC_ALL",
        "LOGNAME",
        "PATH",
        "SHELL",
        "SSL_CERT_FILE",
        "TMPDIR",
        "USER",
    }
    credential = {
        "claude": "ANTHROPIC_API_KEY",
        "codex": "OPENAI_API_KEY",
        "cursor": "CURSOR_API_KEY",
    }[spec.agent]
    names.add(credential)
    if spec.tools:
        names.update(("TYPESAFE_API_KEY", "TYPESAFE_BASE_URL"))
    return {name: os.environ[name] for name in names if name in os.environ}


def run_process(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    stdout_path: Path,
    stderr_path: Path,
    env: Mapping[str, str] | None = None,
) -> ProcessResult:
    started = time.monotonic()
    timed_out = False
    returncode: int | None = None
    status = "ok"
    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                list(command),
                cwd=cwd,
                env=dict(env) if env is not None else None,
                stdout=stdout,
                stderr=stderr,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                returncode = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                status = "timeout"
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                returncode = process.returncode
            if not timed_out and returncode != 0:
                status = "process_error"
    except OSError as exc:
        status = "launch_error"
        stderr_path.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
    return ProcessResult(
        infrastructure_status=status,
        returncode=returncode,
        timed_out=timed_out,
        duration_seconds=time.monotonic() - started,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
    )


def run_unittest(workspace: Path, suite: str, log_dir: Path, timeout: int) -> TestResult:
    stdout_path = log_dir / f"{suite}-tests.stdout"
    stderr_path = log_dir / f"{suite}-tests.stderr"
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        os.pathsep.join((str(workspace), existing_pythonpath))
        if existing_pythonpath
        else str(workspace)
    )
    result = run_process(
        [sys.executable, "-m", "unittest", "discover", "-s", suite, "-v"],
        cwd=workspace,
        timeout=min(timeout, 120),
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        env=env,
    )
    return TestResult(
        passed=result.infrastructure_status == "ok",
        returncode=result.returncode,
        duration_seconds=result.duration_seconds,
        stdout_path=result.stdout_path,
        stderr_path=result.stderr_path,
    )


def score_workspace(spec: RunSpec, workspace: Path, run_dir: Path, timeout: int) -> dict[str, Any]:
    visible = run_unittest(workspace, "tests", run_dir, timeout)
    hidden_target = workspace / "hidden_tests"
    if hidden_target.exists():
        raise RuntimeError("hidden tests existed before scorer injection")
    shutil.copytree(spec.fixture.hidden, hidden_target)
    hidden = run_unittest(workspace, "hidden_tests", run_dir, timeout)
    success = visible.passed and hidden.passed
    return {
        "visible_pass": visible.passed,
        "hidden_pass": hidden.passed,
        "success": success,
        "regression": spec.fixture.initial_visible_pass and not visible.passed,
        "visible_duration_seconds": visible.duration_seconds,
        "hidden_duration_seconds": hidden.duration_seconds,
        "test_duration_seconds": visible.duration_seconds + hidden.duration_seconds,
        "visible_test_logs": {"stdout": visible.stdout_path, "stderr": visible.stderr_path},
        "hidden_test_logs": {"stdout": hidden.stdout_path, "stderr": hidden.stderr_path},
    }


def combine_run_success(process: ProcessResult, score: Mapping[str, Any]) -> bool:
    """A task succeeds only when agent infrastructure and acceptance checks succeed."""
    return process.infrastructure_status == "ok" and bool(score["success"])


def _json_documents(path: Path) -> list[Any]:
    documents: list[Any] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        documents.append(json.loads(text))
        return documents
    except json.JSONDecodeError:
        pass
    for line in text.splitlines():
        try:
            documents.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return documents


def _walk(value: Any) -> Iterable[tuple[str | None, Any, Mapping[str, Any] | None]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key), child, value
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield None, child, None
            yield from _walk(child)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    return None


def parse_agent_metrics(path: Path) -> ParsedMetrics:
    documents = _json_documents(path)
    terminal_usage: list[Mapping[str, Any]] = []
    costs: list[float] = []
    tool_calls: Counter[str] = Counter()
    iterations = 0
    escalations = 0
    reported_turns: list[int] = []
    seen_tool_ids: set[str] = set()

    def visit_tool_calls(value: Any) -> None:
        if isinstance(value, Mapping):
            kind = str(value.get("type", value.get("event", ""))).lower().replace("-", "_")
            name = value.get("name", value.get("tool_name", value.get("tool")))
            if (
                isinstance(name, str)
                and kind in {"tool_use", "tool_call", "mcp_tool_call", "mcp_tool_use"}
            ):
                identity = str(value.get("id", value.get("call_id", f"{kind}:{name}:{id(value)}")))
                if identity not in seen_tool_ids:
                    seen_tool_ids.add(identity)
                    tool_calls[name.split("mcp__jev__")[-1]] += 1
            for key, child in value.items():
                if key == "mcpToolCall" and isinstance(child, Mapping):
                    args = child.get("args")
                    cursor_name = args.get("name") if isinstance(args, Mapping) else None
                    if isinstance(cursor_name, str):
                        identity = str(
                            (args or {}).get(
                                "toolCallId",
                                value.get("toolCallId", f"cursor:{cursor_name}:{id(child)}"),
                            )
                        )
                        if identity not in seen_tool_ids:
                            seen_tool_ids.add(identity)
                            normalized_name = cursor_name.removeprefix("jev-")
                            tool_calls[normalized_name] += 1
                visit_tool_calls(child)
        elif isinstance(value, list):
            for child in value:
                visit_tool_calls(child)

    for document in documents:
        if not isinstance(document, Mapping):
            continue
        event = str(document.get("type", document.get("event", ""))).lower().replace("-", "_")
        usage = document.get("usage")
        if event in {"result", "turn_completed", "turn.completed"} and isinstance(usage, Mapping):
            terminal_usage.append(usage)
        cost = _number(
            document.get(
                "total_cost_usd",
                document.get("cost_usd", document.get("reported_cost_usd")),
            )
        )
        if cost is not None:
            costs.append(cost)
        turns = document.get("num_turns")
        if isinstance(turns, int) and not isinstance(turns, bool):
            reported_turns.append(turns)
        if event == "assistant":
            iterations += 1
        elif event == "item.completed":
            item = document.get("item")
            if isinstance(item, Mapping) and item.get("type") == "agent_message":
                iterations += 1
        visit_tool_calls(document)
        for key, value, _parent in _walk(document):
            normalized = (key or "").lower().replace("-", "_")
            event_value = str(value).lower().replace("-", "_") if isinstance(value, str) else ""
            if normalized in {"type", "event", "event_type"} and event_value in {
                "ask_user",
                "ask_user_question",
                "request_user_input",
                "elicitation_request",
            }:
                escalations += 1

    def usage_total(*keys: str) -> int | None:
        values = []
        for usage in terminal_usage:
            for key in keys:
                number = _number(usage.get(key))
                if number is not None:
                    values.append(int(number))
                    break
        return sum(values) if values else None

    input_tokens = usage_total("input_tokens", "prompt_tokens")
    output_tokens = usage_total("output_tokens", "completion_tokens")
    additive_cache_tokens = usage_total(
        "cache_read_input_tokens"
    )
    cache_creation_tokens = usage_total("cache_creation_input_tokens")
    if cache_creation_tokens is not None:
        additive_cache_tokens = (additive_cache_tokens or 0) + cache_creation_tokens
    subset_cache_tokens = usage_total("cached_input_tokens", "cache_tokens")
    cache_tokens = (
        (additive_cache_tokens or 0) + (subset_cache_tokens or 0)
        if additive_cache_tokens is not None or subset_cache_tokens is not None
        else None
    )
    total_tokens = usage_total("total_tokens")
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        # Anthropic reports cache read/creation separately; Codex's cached_input_tokens
        # is already a subset of input_tokens.
        total_tokens = (input_tokens or 0) + (output_tokens or 0) + (additive_cache_tokens or 0)
    jev = {name: count for name, count in tool_calls.items() if name in ALL_JEV_TOOLS}
    return ParsedMetrics(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_tokens=cache_tokens,
        total_tokens=total_tokens,
        reported_cost_usd=sum(costs) if costs else None,
        tool_calls=dict(tool_calls),
        jev_calls=jev,
        iterations=max(reported_turns) if reported_turns else (iterations or None),
        human_escalations=escalations if documents else None,
    )


def _sum_available(rows: Sequence[Mapping[str, Any]], key: str) -> int | float | None:
    values = [row["metrics"].get(key) for row in rows]
    return sum(values) if values and all(value is not None for value in values) else None


def _bootstrap(
    rows: Sequence[Mapping[str, Any]],
    statistic,
    *,
    seed: int,
    samples: int = 2000,
) -> list[float] | None:
    if not rows:
        return None
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(samples):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        value = statistic(sample)
        if value is not None and math.isfinite(value):
            values.append(float(value))
    if not values:
        return None
    values.sort()
    low = values[int(0.025 * (len(values) - 1))]
    high = values[int(0.975 * (len(values) - 1))]
    return [low, high]


def aggregate(rows: Sequence[Mapping[str, Any]], seed: int) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["agent"]), str(row["condition"]))].append(row)
    result: list[dict[str, Any]] = []
    for offset, ((agent, condition), group) in enumerate(sorted(groups.items())):
        valid = [row for row in group if row.get("infrastructure_status", "ok") == "ok"]
        successes = sum(bool(row["success"]) for row in valid)
        tokens = _sum_available(valid, "total_tokens")
        costs = _sum_available(valid, "reported_cost_usd")
        per_success_tokens = tokens / successes if tokens is not None and successes else None
        per_success_cost = costs / successes if costs is not None and successes else None
        jev_calls: Counter[str] = Counter()
        for row in valid:
            jev_calls.update(row["metrics"].get("jev_calls") or {})

        def success_rate(sample):
            return sum(bool(row["success"]) for row in sample) / len(sample)

        def sampled_tokens_per_success(sample):
            count = sum(bool(row["success"]) for row in sample)
            values = [row["metrics"].get("total_tokens") for row in sample]
            return sum(values) / count if count and all(value is not None for value in values) else None

        result.append(
            {
                "agent": agent,
                "condition": condition,
                "attempts": len(valid),
                "observations": len(group),
                "infrastructure_failures": len(group) - len(valid),
                "successes": successes,
                "success_rate": successes / len(valid) if valid else None,
                "success_rate_bootstrap_95_ci": _bootstrap(
                    valid, success_rate, seed=seed + offset * 2
                )
                if valid
                else None,
                "input_tokens": _sum_available(valid, "input_tokens"),
                "output_tokens": _sum_available(valid, "output_tokens"),
                "cache_tokens": _sum_available(valid, "cache_tokens"),
                "total_tokens": tokens,
                "reported_cost_usd": costs,
                "tokens_per_successful_task": per_success_tokens,
                "tokens_per_successful_task_bootstrap_95_ci": _bootstrap(
                    valid, sampled_tokens_per_success, seed=seed + offset * 2 + 1
                )
                if tokens is not None
                else None,
                "cost_per_successful_task_usd": per_success_cost,
                "jev_calls": dict(jev_calls) if jev_calls else None,
                "duration_seconds": (
                    sum(float(row["duration_seconds"]) for row in valid) if valid else None
                ),
                "iterations": _sum_available(valid, "iterations"),
                "human_escalations": _sum_available(valid, "human_escalations"),
            }
        )
    return result


def execute(specs: Sequence[RunSpec], options: PilotOptions) -> dict[str, Any]:
    if any(spec.tools for spec in specs) and not os.environ.get("TYPESAFE_API_KEY"):
        raise RuntimeError("TYPESAFE_API_KEY is required for live Jev conditions (B, C, or D)")
    options.out.mkdir(parents=True, exist_ok=True)
    rows_path = options.out / "runs.jsonl"
    rows: list[dict[str, Any]] = []
    consecutive_infra_failures = 0
    process_attempts = 0
    stopped_early = False
    with rows_path.open("w", encoding="utf-8") as rows_file:
        for sequence, spec in enumerate(specs, 1):
            final_process: ProcessResult | None = None
            final_score: dict[str, Any] | None = None
            final_metrics: ParsedMetrics | None = None
            attempts: list[dict[str, Any]] = []
            for retry in range(2):
                if process_attempts >= MAX_TOTAL_RUNS:
                    stopped_early = True
                    break
                process_attempts += 1
                run_dir, workspace, config = prepare_workspace(spec, options.out, sequence, retry)
                stdout = run_dir / "agent.stdout"
                stderr = run_dir / "agent.stderr"
                process = run_process(
                    build_agent_command(spec, workspace, config, options),
                    cwd=workspace,
                    timeout=options.timeout,
                    stdout_path=stdout,
                    stderr_path=stderr,
                    env=agent_environment(spec),
                )
                score = score_workspace(spec, workspace, run_dir, options.timeout)
                metrics = parse_agent_metrics(stdout)
                attempts.append(
                    {
                        "retry": retry,
                        "workspace": str(workspace),
                        "process": asdict(process),
                        "score": score,
                    }
                )
                final_process, final_score, final_metrics = process, score, metrics
                if process.infrastructure_status == "ok":
                    consecutive_infra_failures = 0
                    break
                consecutive_infra_failures += 1
                if consecutive_infra_failures >= 3:
                    stopped_early = True
                    break
            if final_process is None or final_score is None or final_metrics is None:
                break
            row = {
                "run_id": f"{sequence:03d}-{uuid.uuid4().hex[:12]}",
                "agent": spec.agent,
                "condition": spec.condition,
                "task": spec.fixture.name,
                "allowed_jev_tools": list(spec.tools),
                "infrastructure_status": final_process.infrastructure_status,
                "returncode": final_process.returncode,
                "retry_count": len(attempts) - 1,
                "attempt_logs": attempts,
                **final_score,
                "success": combine_run_success(final_process, final_score),
                "duration_seconds": final_process.duration_seconds + final_score["test_duration_seconds"],
                "metrics": asdict(final_metrics),
                "metadata": {
                    "cursor_per_tool_filtering": False if spec.agent == "cursor" and spec.tools else None,
                    "cursor_tool_policy_enforced_by_prompt": bool(spec.agent == "cursor" and spec.tools),
                    "hidden_injected_after_agent_exit": True,
                },
            }
            rows.append(row)
            rows_file.write(json.dumps(row, sort_keys=True) + "\n")
            rows_file.flush()
            if stopped_early:
                break
    summary = {
        "kind": "agent_pilot",
        "seed": options.seed,
        "planned_runs": len(specs),
        "completed_runs": len(rows),
        "agent_process_attempts": process_attempts,
        "stopped_early": stopped_early,
        "stop_reason": "three_consecutive_infrastructure_failures_or_run_cap" if stopped_early else None,
        "rows_file": str(rows_path),
        "aggregates": aggregate(rows, options.seed),
    }
    (options.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def _auth_check(command: Sequence[str]) -> dict[str, Any]:
    binary = shutil.which(command[0])
    if not binary:
        return {"binary": False, "authenticated": False, "action": f"Install {command[0]} and add it to PATH."}
    try:
        result = subprocess.run(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"binary": True, "authenticated": False, "action": f"Run {command[0]}'s login command."}
    authenticated = result.returncode == 0
    return {
        "binary": True,
        "authenticated": authenticated,
        "action": None if authenticated else f"Authenticate {command[0]} before --execute.",
    }


def preflight(agents: Sequence[str], conditions: Sequence[str]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    commands = {
        "claude": ("claude", "auth", "status"),
        "codex": ("codex", "login", "status"),
        "cursor": ("cursor-agent", "status"),
    }
    for agent in agents:
        checks[agent] = _auth_check(commands[agent])
    if "cursor" in checks and checks["cursor"]["authenticated"]:
        models = subprocess.run(
            ["cursor-agent", "models"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        has_models = models.returncode == 0 and "No models available" not in (
            models.stdout + models.stderr
        )
        checks["cursor"]["models_available"] = has_models
        if not has_models:
            checks["cursor"]["action"] = (
                "Cursor CLI account exposes no models; use external Cursor-subagent runs "
                "or fix account entitlement."
            )
    needs_key = any(CONDITIONS[condition] for condition in conditions)
    key_present = bool(os.environ.get("TYPESAFE_API_KEY"))
    return {
        "ok": all(
            check["binary"]
            and check["authenticated"]
            and check.get("models_available", True)
            for check in checks.values()
        )
        and (key_present or not needs_key),
        "agents": checks,
        "typesafe_api_key_present": key_present,
        "typesafe_api_key_required": needs_key,
        "typesafe_action": None
        if key_present or not needs_key
        else "Set TYPESAFE_API_KEY in the environment before running live Jev conditions.",
    }
