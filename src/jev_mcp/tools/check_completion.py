from __future__ import annotations

from typing import Any

from jev_mcp.engine import Engine
from jev_mcp.models import (
    ClientMeta,
    ImplementationInput,
    JudgmentQuestion,
    TaskInput,
    VerificationInput,
)
from jev_mcp.normalization.diffs import normalize_diff
from jev_mcp.normalization.requirements import normalize_requirement_text
from jev_mcp.normalization.text import normalize_text
from jev_mcp.policy.decisions import completion_status, completion_user_decision
from jev_mcp.tools._common import char_count, client_or_default, require_predefined_goal
from jev_mcp.util.limits import LimitReport, enforce_count

TOOL_NAME = "jev_check_completion"
TOOL_VERSION = "1.0.0"
DESCRIPTION = (
    "Help the user decide whether the current attempt reached a predefined goal. "
    "Cheap requirement/evidence coverage check before an expensive full-task review. "
    "Returns per-requirement likelihoods, review list, and user_decision. "
    "Never certifies correctness, safety, or merge readiness."
)

FORBIDDEN_STATUSES = {"APPROVED", "CORRECT", "SAFE_TO_MERGE", "SECURE"}


def _requirement_questions(req_id: str) -> list[JudgmentQuestion]:
    return [
        JudgmentQuestion(
            id=f"{req_id}::appears_satisfied",
            question=(
                f"Does the supplied implementation and verification evidence suggest "
                f"requirement {req_id} appears satisfied?"
            ),
        ),
        JudgmentQuestion(
            id=f"{req_id}::evidence_present",
            question=(
                f"Does the supplied evidence include concrete verification or implementation "
                f"support for requirement {req_id}?"
            ),
        ),
        JudgmentQuestion(
            id=f"{req_id}::possible_gap",
            question=(
                f"Does the supplied evidence suggest a possible gap remaining for requirement {req_id}?"
            ),
        ),
    ]


GLOBAL_QUESTIONS = [
    JudgmentQuestion(
        id="scope_appropriate",
        question=(
            "Does the supplied evidence suggest the implementation scope is appropriate "
            "for the stated task goal?"
        ),
    ),
    JudgmentQuestion(
        id="unresolved_requirement",
        question=(
            "Does the supplied evidence suggest at least one stated requirement remains unresolved?"
        ),
    ),
    JudgmentQuestion(
        id="further_review_warranted",
        question=(
            "Does the supplied evidence suggest further human or frontier review is warranted "
            "before treating the task as complete?"
        ),
    ),
]


async def run_check_completion(
    engine: Engine,
    *,
    task: TaskInput | dict[str, Any],
    implementation: ImplementationInput | dict[str, Any],
    verification: VerificationInput | dict[str, Any] | None = None,
    client: ClientMeta | dict | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    task_model = TaskInput.model_validate(task)
    task_model.goal = require_predefined_goal(task_model.goal)
    impl = ImplementationInput.model_validate(implementation)
    verify = VerificationInput.model_validate(verification or {})
    client_meta = client_or_default(client)
    limits = engine.config.limits
    requirements, req_warnings = enforce_count(
        task_model.requirements, limits.max_requirements, label="requirements"
    )
    diff, diff_report = normalize_diff(impl.diff_summary, limits.max_state_chars // 3)
    report = LimitReport().merge(diff_report)

    questions = list(GLOBAL_QUESTIONS)
    for item in requirements:
        questions.extend(_requirement_questions(item.id))

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
            "implementation": {
                "changed_files": impl.changed_files,
                "diff_summary": diff,
            },
            "verification": {
                "tests": normalize_text(verify.tests),
                "lint": normalize_text(verify.lint),
                "typecheck": normalize_text(verify.typecheck),
                "other": [normalize_text(item) for item in verify.other],
            },
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
        original_chars=char_count(task_model, impl, verify),
        warnings=report.warnings + req_warnings,
    )

    per_req: dict[str, dict[str, float]] = {}
    for item in requirements:
        per_req[item.id] = {
            "appears_satisfied": result.answers[f"{item.id}::appears_satisfied"],
            "evidence_present": result.answers[f"{item.id}::evidence_present"],
            "possible_gap": result.answers[f"{item.id}::possible_gap"],
        }
    signals = {
        "scope_appropriate": result.answers["scope_appropriate"],
        "unresolved_requirement": result.answers["unresolved_requirement"],
        "further_review_warranted": result.answers["further_review_warranted"],
    }
    status, review = completion_status(per_req, signals, engine.config.thresholds.default)
    if status in FORBIDDEN_STATUSES:
        status = "REVIEW_REQUIRED"
    return engine.finalize(
        {
            "requirements": per_req,
            "signals": signals,
            "status": status,
            "review_requirements": review,
            "user_decision": completion_user_decision(status),
            "meta": engine.meta(result, cached=cached, request_id=request_id, tool=TOOL_NAME),
        },
        warnings=report.warnings + req_warnings,
    )
