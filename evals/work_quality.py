"""Coding and planning work preservation. Spec-follow vs Jev-as-gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jev_mcp.config import AppConfig
from jev_mcp.engine import Engine
from jev_mcp.errors import JevError
from jev_mcp.providers.mock import MockJudgmentProvider
from jev_mcp.tools.check_completion import run_check_completion
from jev_mcp.tools.judge import reject_generative, run_judge
from jev_mcp.tools.rank_context import run_rank_context
from jev_mcp.tools.triage_failure import run_triage_failure


def _engine(tmp: Path, answers: dict[str, float]) -> Engine:
    config = AppConfig.model_validate(
        {
            "provider": {"name": "mock"},
            "data_dir": str(tmp),
            "cache": {"enabled": False},
            "server": {"shadow_mode": True},
        }
    )
    return Engine.create(config, provider=MockJudgmentProvider(answers=answers, default=0.5))


def spec_keeps_red_test(exit_code: int, _signals: dict[str, float]) -> bool:
    """Deterministic evidence first: a failing command stays in scope."""
    return exit_code != 0


def blind_skips_red_test(exit_code: int, signals: dict[str, float]) -> bool:
    return (
        exit_code != 0
        and signals.get("likely_preexisting", 0) >= 0.70
        and signals.get("related_to_current_change", 1) <= 0.30
    )


async def coding_do_not_skip_failing_test(tmp: Path) -> dict[str, Any]:
    engine = _engine(
        tmp,
        {
            "related_to_current_change": 0.08,
            "likely_localized": 0.20,
            "likely_preexisting": 0.94,
            "requirement_related": 0.12,
            "same_as_previous_failure": 0.10,
            "needs_deeper_reasoning": 0.22,
        },
    )
    try:
        result = await run_triage_failure(
            engine,
            task={
                "goal": "Add guest checkout",
                "requirements": [{"id": "R14", "text": "Guest order must resolve a canonical user"}],
            },
            current_step="Implement webhook identity",
            failure={
                "command": "pnpm test",
                "exit_code": 1,
                "summary": "guest_identity expected UUID but received null",
                "output": "FAIL stripe.test.ts",
            },
            changed_files=["src/webhooks/stripe.ts"],
            diff_summary="rename helper",
        )
    finally:
        await engine.close()
    signals = result["signals"]
    return {
        "id": "coding-keep-red-test",
        "kind": "coding",
        "spec_lost_work": 0 if spec_keeps_red_test(1, signals) else 1,
        "blind_lost_work": 1 if blind_skips_red_test(1, signals) else 0,
        "note": "exit_code=1 stays in scope even if Jev says preexisting / unrelated.",
    }


async def coding_do_not_ship_incomplete_impl(tmp: Path) -> dict[str, Any]:
    engine = _engine(
        tmp,
        {
            "R1::appears_satisfied": 0.92,
            "R1::evidence_present": 0.90,
            "R1::possible_gap": 0.08,
            "R2::appears_satisfied": 0.12,
            "R2::evidence_present": 0.10,
            "R2::possible_gap": 0.88,
            "R3::appears_satisfied": 0.20,
            "R3::evidence_present": 0.15,
            "R3::possible_gap": 0.80,
            "scope_appropriate": 0.40,
            "unresolved_requirement": 0.91,
            "further_review_warranted": 0.86,
        },
    )
    try:
        result = await run_check_completion(
            engine,
            task={
                "goal": "Guest checkout",
                "requirements": [
                    {"id": "R1", "text": "Rename the helper"},
                    {"id": "R2", "text": "Resolve canonical user on guest order"},
                    {"id": "R3", "text": "Cover guest identity with a test"},
                ],
            },
            implementation={"changed_files": ["src/webhooks/stripe.ts"], "diff_summary": "rename helper"},
            verification={"tests": "", "lint": "ok", "typecheck": "ok"},
        )
    finally:
        await engine.close()
    review = set(result.get("review_requirements") or [])
    needed = {"R2", "R3"}
    spec_miss = len(needed - review)
    blind_ship = result.get("status") != "INCOMPLETE"
    return {
        "id": "coding-do-not-ship-partial",
        "kind": "coding",
        "spec_lost_work": spec_miss,
        "blind_lost_work": len(needed) if blind_ship else spec_miss,
        "status": result.get("status"),
        "note": "Partial impl + empty tests must not become a ship decision.",
    }


async def planning_do_not_drop_backlog_items(tmp: Path) -> dict[str, Any]:
    engine = _engine(
        tmp,
        {
            "P1::relevant_to_task": 0.95,
            "P1::useful_now": 0.90,
            "P1::likely_noise": 0.05,
            "P2::relevant_to_task": 0.20,
            "P2::useful_now": 0.15,
            "P2::likely_noise": 0.80,
            "P3::relevant_to_task": 0.88,
            "P3::useful_now": 0.40,
            "P3::likely_noise": 0.25,
        },
    )
    plan = [
        {"id": "P1", "path": "plan/checkout.md", "content": "Must resolve canonical guest user"},
        {"id": "P2", "path": "plan/marketing.md", "content": "Launch blog post after GA"},
        {"id": "P3", "path": "plan/refunds.md", "content": "Refunds must keep audit trail"},
    ]
    try:
        result = await run_rank_context(
            engine,
            task_goal="Ship guest checkout this quarter",
            current_step="Sequence the delivery plan",
            candidates=plan,
        )
    finally:
        await engine.close()
    remaining = {row["id"] for row in result["candidates"]}
    high = {row["id"] for row in result["candidates"] if row["tier"] == "HIGH"}
    required = {"P1", "P3"}
    return {
        "id": "planning-keep-backlog",
        "kind": "planning",
        "spec_lost_work": len(required - remaining),
        "blind_lost_work": len(required - high),
        "note": "LOW/MEDIUM plan items stay on the list. Blind planning drops them.",
    }


def planning_rejects_generative_and_product_decisions() -> dict[str, Any]:
    banned = [
        "write a sprint plan for guest checkout",
        "draft the Q3 roadmap",
        "create the backlog",
        "should we enter the EU market",
        "which architecture should we use",
        "choose between a marketplace and a single-vendor model",
        "prioritize growth over checkout reliability",
        "decide the pricing strategy",
    ]
    allowed = [
        "Does the supplied evidence suggest the plan lists guest checkout?",
        "Does the supplied evidence suggest milestone M2 depends on M1?",
    ]
    rejected = 0
    leaked = 0
    for question in banned:
        try:
            reject_generative(question)
            leaked += 1
        except JevError:
            rejected += 1
    allowed_ok = 0
    for question in allowed:
        reject_generative(question)
        allowed_ok += 1
    return {
        "id": "planning-reject-decisions",
        "kind": "planning",
        "spec_lost_work": leaked,
        "blind_lost_work": len(banned) - rejected,
        "rejected": rejected,
        "banned": len(banned),
        "allowed_ok": allowed_ok,
        "note": "Jev must refuse to write plans or pick business/architecture options.",
    }


async def planning_judge_refuses_in_engine(tmp: Path) -> dict[str, Any]:
    engine = _engine(tmp, {"Q1": 0.9})
    leaked = 1
    code = None
    try:
        result = await run_judge(
            engine,
            state={"brief": "Expand to EU in Q3"},
            questions=[{"id": "Q1", "question": "should we enter the EU market"}],
        )
        leaked = 0 if "error" in result else 1
        code = (result.get("error") or {}).get("code")
    except JevError as exc:
        leaked = 0
        code = str(exc.code)
    finally:
        await engine.close()
    return {
        "id": "planning-judge-tool-refuses",
        "kind": "planning",
        "spec_lost_work": leaked,
        "blind_lost_work": leaked,
        "error_code": code,
        "note": "A product-decision question must not return a probability.",
    }


async def run_work_quality(tmp: Path) -> dict[str, Any]:
    rows = [
        await coding_do_not_skip_failing_test(tmp),
        await coding_do_not_ship_incomplete_impl(tmp),
        await planning_do_not_drop_backlog_items(tmp),
        planning_rejects_generative_and_product_decisions(),
        await planning_judge_refuses_in_engine(tmp),
    ]
    spec = sum(row["spec_lost_work"] for row in rows)
    blind = sum(row["blind_lost_work"] for row in rows)
    return {
        "kind": "coding_and_planning_work_preservation",
        "disclaimer": (
            "Simulated agent policies on coding/planning fixtures. Not a live multi-day "
            "coding or business-planning bakeoff."
        ),
        "spec_lost_work": spec,
        "blind_lost_work": blind,
        "rows": rows,
    }
