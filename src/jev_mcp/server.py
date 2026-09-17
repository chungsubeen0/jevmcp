"""MCP stdio server. TypeSafe is not contacted at startup."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from jev_mcp import __version__
from jev_mcp.config import AppConfig, load_config
from jev_mcp.engine import Engine
from jev_mcp.models import (
    Attempt,
    ClientMeta,
    ContextCandidate,
    FailureEvent,
    Finding,
    ImplementationInput,
    JudgeQuestion,
    PreviousFailure,
    Requirement,
    TaskInput,
    VerificationInput,
)
from jev_mcp.telemetry.privacy import SecretLogFilter
from jev_mcp.tools._common import safe_run
from jev_mcp.tools.assess_risk import DESCRIPTION as ASSESS_RISK_DESCRIPTION
from jev_mcp.tools.assess_risk import run_assess_risk
from jev_mcp.tools.check_completion import DESCRIPTION as CHECK_COMPLETION_DESCRIPTION
from jev_mcp.tools.check_completion import run_check_completion
from jev_mcp.tools.classify_findings import DESCRIPTION as CLASSIFY_FINDINGS_DESCRIPTION
from jev_mcp.tools.classify_findings import run_classify_findings
from jev_mcp.tools.compare_attempts import DESCRIPTION as COMPARE_ATTEMPTS_DESCRIPTION
from jev_mcp.tools.compare_attempts import run_compare_attempts
from jev_mcp.tools.judge import DESCRIPTION as JUDGE_DESCRIPTION
from jev_mcp.tools.judge import run_judge
from jev_mcp.tools.rank_context import DESCRIPTION as RANK_CONTEXT_DESCRIPTION
from jev_mcp.tools.rank_context import run_rank_context
from jev_mcp.tools.triage_failure import DESCRIPTION as TRIAGE_FAILURE_DESCRIPTION
from jev_mcp.tools.triage_failure import run_triage_failure

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # mcp >= 2
    from mcp.server import MCPServer as FastMCP

_ENGINE: Engine | None = None
mcp = FastMCP("jev-mcp")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    secret_filter = SecretLogFilter()
    logging.getLogger().addFilter(secret_filter)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx").addFilter(secret_filter)


def get_engine() -> Engine:
    if _ENGINE is None:
        raise RuntimeError("Jev MCP engine is not initialized")
    return _ENGINE


def init_engine(config: AppConfig, *, provider=None) -> Engine:
    global _ENGINE
    configure_logging(config.server.log_level)
    _ENGINE = Engine.create(config, provider=provider)
    logging.getLogger("jev_mcp").info(
        "Jev MCP %s ready provider=%s profile=%s shadow=%s",
        __version__,
        config.provider.name,
        config.profile.default,
        config.server.shadow_mode,
    )
    return _ENGINE


@mcp.tool(name="jev_triage_failure", description=TRIAGE_FAILURE_DESCRIPTION)
async def jev_triage_failure(
    task: TaskInput,
    current_step: str,
    failure: FailureEvent,
    changed_files: list[str] | None = None,
    diff_summary: str = "",
    previous_failure: PreviousFailure | None = None,
    client: ClientMeta | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    return await safe_run(
        lambda: run_triage_failure(
            get_engine(),
            task=task,
            current_step=current_step,
            failure=failure,
            changed_files=changed_files,
            diff_summary=diff_summary,
            previous_failure=previous_failure,
            client=client,
            use_cache=use_cache,
        )
    )


@mcp.tool(name="jev_compare_attempts", description=COMPARE_ATTEMPTS_DESCRIPTION)
async def jev_compare_attempts(
    task_goal: str,
    previous_attempt: Attempt,
    current_attempt: Attempt,
    client: ClientMeta | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    return await safe_run(
        lambda: run_compare_attempts(
            get_engine(),
            task_goal=task_goal,
            previous_attempt=previous_attempt,
            current_attempt=current_attempt,
            client=client,
            use_cache=use_cache,
        )
    )


@mcp.tool(name="jev_check_completion", description=CHECK_COMPLETION_DESCRIPTION)
async def jev_check_completion(
    task: TaskInput,
    implementation: ImplementationInput,
    verification: VerificationInput | None = None,
    client: ClientMeta | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    return await safe_run(
        lambda: run_check_completion(
            get_engine(),
            task=task,
            implementation=implementation,
            verification=verification,
            client=client,
            use_cache=use_cache,
        )
    )


@mcp.tool(name="jev_rank_context", description=RANK_CONTEXT_DESCRIPTION)
async def jev_rank_context(
    task_goal: str,
    current_step: str,
    candidates: list[ContextCandidate],
    client: ClientMeta | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    return await safe_run(
        lambda: run_rank_context(
            get_engine(),
            task_goal=task_goal,
            current_step=current_step,
            candidates=candidates,
            client=client,
            use_cache=use_cache,
        )
    )


@mcp.tool(name="jev_classify_findings", description=CLASSIFY_FINDINGS_DESCRIPTION)
async def jev_classify_findings(
    task_goal: str,
    findings: list[Finding],
    requirements: list[Requirement] | None = None,
    client: ClientMeta | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    return await safe_run(
        lambda: run_classify_findings(
            get_engine(),
            task_goal=task_goal,
            findings=findings,
            requirements=requirements,
            client=client,
            use_cache=use_cache,
        )
    )


@mcp.tool(name="jev_assess_risk", description=ASSESS_RISK_DESCRIPTION)
async def jev_assess_risk(
    task_goal: str,
    changed_files: list[str] | None = None,
    diff_summary: str = "",
    requirements: list[Requirement] | None = None,
    client: ClientMeta | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    return await safe_run(
        lambda: run_assess_risk(
            get_engine(),
            task_goal=task_goal,
            changed_files=changed_files,
            diff_summary=diff_summary,
            requirements=requirements,
            client=client,
            use_cache=use_cache,
        )
    )


@mcp.tool(name="jev_judge", description=JUDGE_DESCRIPTION)
async def jev_judge(
    state: dict[str, Any],
    questions: list[JudgeQuestion],
    client: ClientMeta | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    return await safe_run(
        lambda: run_judge(
            get_engine(),
            state=state,
            questions=questions,
            client=client,
            use_cache=use_cache,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jev MCP server")
    parser.add_argument("--config", help="Path to a YAML config file")
    parser.add_argument("--provider", choices=["typesafe", "mock"])
    parser.add_argument("--profile", choices=["autonomous", "interactive", "custom"])
    parser.add_argument("--shadow", action="store_true", help="Enable shadow mode")
    parser.add_argument("--log-level", dest="log_level")
    return parser


def config_from_args(args: argparse.Namespace) -> AppConfig:
    overrides: dict[str, Any] = {}
    if args.provider:
        overrides.setdefault("provider", {})["name"] = args.provider
    if args.profile:
        overrides.setdefault("profile", {})["default"] = args.profile
    if args.shadow:
        overrides.setdefault("server", {})["shadow_mode"] = True
    if args.log_level:
        overrides.setdefault("server", {})["log_level"] = args.log_level
    return load_config(config_path=args.config, cli_overrides=overrides or None)


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    config = config_from_args(args)
    init_engine(config)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
