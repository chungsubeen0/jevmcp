from __future__ import annotations

from typing import Any

from jev_mcp.engine import Engine
from jev_mcp.models import (
    ClientMeta,
    FailureEvent,
    JudgmentQuestion,
    PreviousFailure,
    TaskInput,
)
from jev_mcp.normalization.diffs import normalize_diff
from jev_mcp.normalization.failures import normalize_failure_output
from jev_mcp.normalization.requirements import normalize_requirement_text
from jev_mcp.normalization.text import normalize_text
from jev_mcp.policy.decisions import triage_classification, triage_user_decision
from jev_mcp.tools._common import char_count, client_or_default, engine_profile, require_predefined_goal
from jev_mcp.util.limits import LimitReport, enforce_count

TOOL_NAME = "jev_triage_failure"
TOOL_VERSION = "1.0.0"
DESCRIPTION = (
    "Help the user decide the next implementation attempt toward a predefined goal "
    "after a failure. Cheap triage for test/build/lint/typecheck failures. Use before "
    "broad reasoning when scope is unclear. Returns likelihoods and user_decision. "
    "Does not diagnose or fix."
)

QUESTIONS = [
    JudgmentQuestion(
        id="related_to_current_change",
        question=(
            "Does the supplied evidence suggest that the current failure is related to "
            "the current change (changed files and diff)?"
        ),
        criteria={
            "true": "Failure mentions or clearly follows from the changed files or diff",
            "false": "Failure is unrelated to the supplied change evidence",
        },
    ),
    JudgmentQuestion(
        id="likely_localized",
        question=(
            "Does the supplied evidence suggest the failure is localized to the changed "
            "files or immediately adjacent code?"
        ),
    ),
    JudgmentQuestion(
        id="likely_preexisting",
        question=(
            "Does the supplied evidence suggest this failure likely preexisted the current change?"
        ),
    ),
    JudgmentQuestion(
        id="requirement_related",
        question=(
            "Does the supplied evidence suggest the failure is related to a stated task requirement?"
        ),
    ),
    JudgmentQuestion(
        id="same_as_previous_failure",
        question=(
            "Does the supplied evidence suggest the current failure is materially equivalent "
            "to the previous failure?"
        ),
    ),
    JudgmentQuestion(
        id="needs_deeper_reasoning",
        question=(
            "Does the supplied evidence suggest this failure requires deeper reasoning beyond "
            "triage because it is novel, ambiguous, or insufficiently evidenced?"
        ),
    ),
]


async def run_triage_failure(
    engine: Engine,
    *,
    task: TaskInput | dict[str, Any],
    current_step: str,
    failure: FailureEvent | dict[str, Any],
    changed_files: list[str] | None = None,
    diff_summary: str = "",
    previous_failure: PreviousFailure | dict[str, Any] | None = None,
    client: ClientMeta | dict | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    task_model = TaskInput.model_validate(task)
    task_model.goal = require_predefined_goal(task_model.goal)
    failure_model = FailureEvent.model_validate(failure)
    previous = PreviousFailure.model_validate(previous_failure) if previous_failure else None
    client_meta = client_or_default(client)
    profile = engine_profile(engine, client_meta)
    limits = engine.config.limits

    requirements, req_warnings = enforce_count(
        task_model.requirements, limits.max_requirements, label="requirements"
    )
    output, output_report = normalize_failure_output(failure_model.output, limits.max_state_chars // 2)
    diff, diff_report = normalize_diff(diff_summary, limits.max_state_chars // 4)
    report = LimitReport().merge(output_report).merge(diff_report)

    state = engine.attach_state_meta(
        {
            "task": {
                "goal": normalize_text(task_model.goal, strip_progress=False),
                "requirements": [
                    {
                        "id": item.id,
                        "text": normalize_requirement_text(item.text, limits.max_question_chars),
                    }
                    for item in requirements
                ],
            },
            "current_step": normalize_text(current_step, strip_progress=False),
            "failure": {
                "command": failure_model.command,
                "exit_code": failure_model.exit_code,
                "summary": normalize_text(failure_model.summary, strip_progress=False),
                "output": output,
            },
            "changed_files": changed_files or [],
            "diff_summary": diff,
            "previous_failure": {
                "summary": normalize_text(previous.summary, strip_progress=False)
            }
            if previous
            else None,
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
        original_chars=char_count(task_model, current_step, failure_model, diff_summary, previous),
        warnings=report.warnings + req_warnings,
    )
    classification = triage_classification(result.answers, engine.config.thresholds.default, profile)
    return engine.finalize(
        {
            "signals": result.answers,
            "classification": classification,
            "user_decision": triage_user_decision(classification),
            "meta": engine.meta(result, cached=cached, request_id=request_id, tool=TOOL_NAME),
        },
        warnings=report.warnings + req_warnings,
    )
