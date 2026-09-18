from __future__ import annotations

from typing import Any

from jev_mcp.engine import Engine
from jev_mcp.models import ClientMeta, ContextCandidate, JudgmentQuestion
from jev_mcp.normalization.text import normalize_text
from jev_mcp.policy.decisions import context_tier, rank_user_decision
from jev_mcp.tools._common import char_count, client_or_default, engine_profile, require_predefined_goal
from jev_mcp.util.limits import LimitReport, apply_char_limit, enforce_count

TOOL_NAME = "jev_rank_context"
TOOL_VERSION = "1.0.0"
DESCRIPTION = (
    "Help the user decide what to inspect next toward a predefined goal. "
    "Cheap ranking of repository context candidates before deeper frontier inspection. "
    "Ranks only; never deletes or permanently excludes candidates."
)


def _candidate_questions(candidate_id: str) -> list[JudgmentQuestion]:
    return [
        JudgmentQuestion(
            id=f"{candidate_id}::relevant_to_task",
            question=(
                f"Does the supplied evidence suggest candidate {candidate_id} is relevant "
                f"to the current task goal?"
            ),
        ),
        JudgmentQuestion(
            id=f"{candidate_id}::useful_now",
            question=(
                f"Does the supplied evidence suggest candidate {candidate_id} is useful to "
                f"inspect for the current step?"
            ),
        ),
        JudgmentQuestion(
            id=f"{candidate_id}::likely_noise",
            question=(
                f"Does the supplied evidence suggest candidate {candidate_id} is likely noise "
                f"for the current step?"
            ),
        ),
    ]


async def run_rank_context(
    engine: Engine,
    *,
    task_goal: str,
    current_step: str,
    candidates: list[ContextCandidate] | list[dict[str, Any]],
    client: ClientMeta | dict | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    task_goal = require_predefined_goal(task_goal)
    parsed = [ContextCandidate.model_validate(item) for item in candidates]
    client_meta = client_or_default(client)
    profile = engine_profile(engine, client_meta)
    kept, count_warnings = enforce_count(
        parsed, engine.config.limits.max_candidates, label="candidates"
    )
    report = LimitReport()
    questions: list[JudgmentQuestion] = []
    normalized: list[dict[str, Any]] = []
    for item in kept:
        content, content_report = apply_char_limit(
            normalize_text(item.content, strip_progress=False),
            engine.config.limits.max_candidate_chars,
            label=f"candidate {item.id}",
        )
        report = report.merge(content_report)
        normalized.append(
            {
                "id": item.id,
                "path": item.path,
                "symbol": item.symbol,
                "content": content,
            }
        )
        questions.extend(_candidate_questions(item.id))

    state = engine.attach_state_meta(
        {
            "task_goal": normalize_text(task_goal, strip_progress=False),
            "current_step": normalize_text(current_step, strip_progress=False),
            "candidates": normalized,
        },
        report,
    )
    result, cached, request_id = await engine.evaluate(
        tool=TOOL_NAME,
        tool_version=TOOL_VERSION,
        state=state,
        questions=questions,
        client=client_meta,
        use_cache=use_cache,
        original_chars=char_count(task_goal, current_step, parsed),
        warnings=report.warnings + count_warnings,
    )
    ranked = []
    for item in normalized:
        relevant = result.answers[f"{item['id']}::relevant_to_task"]
        useful = result.answers[f"{item['id']}::useful_now"]
        noise = result.answers[f"{item['id']}::likely_noise"]
        ranked.append(
            {
                "id": item["id"],
                "path": item.get("path"),
                "symbol": item.get("symbol"),
                "relevant_to_task": relevant,
                "useful_now": useful,
                "likely_noise": noise,
                "tier": context_tier(relevant, useful, noise, profile),
            }
        )
    ranked.sort(key=lambda row: (-{"HIGH": 2, "MEDIUM": 1, "LOW": 0}[row["tier"]], -row["useful_now"]))
    return engine.finalize(
        {
            "candidates": ranked,
            "user_decision": rank_user_decision(),
            "meta": engine.meta(result, cached=cached, request_id=request_id, tool=TOOL_NAME),
        },
        warnings=report.warnings + count_warnings,
    )
