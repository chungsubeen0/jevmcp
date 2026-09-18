from __future__ import annotations

from typing import Any

from jev_mcp.engine import Engine
from jev_mcp.models import Attempt, ClientMeta, JudgmentQuestion
from jev_mcp.normalization.diffs import normalize_diff
from jev_mcp.normalization.text import normalize_text
from jev_mcp.policy.decisions import attempt_user_decision, stuck_decision
from jev_mcp.tools._common import char_count, client_or_default, engine_profile, require_predefined_goal
from jev_mcp.util.limits import LimitReport

TOOL_NAME = "jev_compare_attempts"
TOOL_VERSION = "1.0.0"
DESCRIPTION = (
    "Help the user decide the next implementation attempt toward a predefined goal. "
    "Compare two unsuccessful attempts. Returns stuck/progress signals, an advisory "
    "control signal, and user_decision text. Does not write the next fix or change the goal."
)

QUESTIONS = [
    JudgmentQuestion(
        id="same_failure",
        question=(
            "Does the supplied evidence suggest the current attempt failed for the same "
            "material reason as the previous attempt?"
        ),
    ),
    JudgmentQuestion(
        id="same_strategy",
        question=(
            "Does the supplied evidence suggest the current attempt used substantially the "
            "same strategy as the previous attempt?"
        ),
    ),
    JudgmentQuestion(
        id="meaningful_new_evidence",
        question=(
            "Does the supplied evidence suggest the current attempt produced meaningful new "
            "evidence that was not available from the previous attempt?"
        ),
    ),
    JudgmentQuestion(
        id="meaningful_progress",
        question=(
            "Does the supplied evidence suggest the current attempt made meaningful progress "
            "toward the stated task goal?"
        ),
    ),
    JudgmentQuestion(
        id="reconsider_approach",
        question=(
            "Does the supplied evidence suggest the user should reconsider the current "
            "approach before another similar attempt toward the stated task goal?"
        ),
    ),
]


def _attempt_state(attempt: Attempt, max_chars: int) -> tuple[dict[str, Any], LimitReport]:
    diff, report = normalize_diff(attempt.diff_summary, max_chars)
    return {
        "hypothesis": normalize_text(attempt.hypothesis, strip_progress=False),
        "approach": normalize_text(attempt.approach, strip_progress=False),
        "changed_files": attempt.changed_files,
        "diff_summary": diff,
        "failure": normalize_text(attempt.failure, strip_progress=False),
    }, report


async def run_compare_attempts(
    engine: Engine,
    *,
    task_goal: str,
    previous_attempt: Attempt | dict[str, Any],
    current_attempt: Attempt | dict[str, Any],
    client: ClientMeta | dict | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    task_goal = require_predefined_goal(task_goal)
    previous = Attempt.model_validate(previous_attempt)
    current = Attempt.model_validate(current_attempt)
    client_meta = client_or_default(client)
    profile = engine_profile(engine, client_meta)
    budget = engine.config.limits.max_state_chars // 3
    prev_state, prev_report = _attempt_state(previous, budget)
    curr_state, curr_report = _attempt_state(current, budget)
    report = prev_report.merge(curr_report)

    state = engine.attach_state_meta(
        {
            "task_goal": normalize_text(task_goal, strip_progress=False),
            "previous_attempt": prev_state,
            "current_attempt": curr_state,
        },
        report,
    )
    result, cached, request_id = await engine.evaluate(
        tool=TOOL_NAME,
        tool_version=TOOL_VERSION,
        state=state,
        questions=QUESTIONS,
        client=client_meta,
        use_cache=use_cache,
        original_chars=char_count(task_goal, previous, current),
        warnings=report.warnings,
    )
    status, signal = stuck_decision(result.answers, engine.config.thresholds.stuck, profile)
    return engine.finalize(
        {
            "signals": result.answers,
            "status": status,
            "control_signal": signal,
            "user_decision": attempt_user_decision(status, signal),
            "meta": engine.meta(result, cached=cached, request_id=request_id, tool=TOOL_NAME),
        },
        warnings=report.warnings,
    )
