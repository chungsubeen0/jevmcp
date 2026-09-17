from __future__ import annotations

from typing import Any

from jev_mcp.engine import Engine
from jev_mcp.models import ClientMeta, Finding, JudgmentQuestion, Requirement
from jev_mcp.normalization.requirements import normalize_requirement_text
from jev_mcp.normalization.text import normalize_text
from jev_mcp.tools._common import char_count, client_or_default
from jev_mcp.util.limits import LimitReport, enforce_count

TOOL_NAME = "jev_classify_findings"
TOOL_VERSION = "1.0.0"
DESCRIPTION = (
    "Cheap normalization of review findings from tests, linters, humans, or frontier reviewers. "
    "Use to triage a large finding set before expensive reasoning. Returns likelihood signals only. "
    "Does not confirm that a vulnerability or defect exists."
)

SIGNAL_IDS = (
    "likely_valid",
    "requirement_related",
    "requires_code_change",
    "requires_replan",
    "likely_duplicate",
    "security_relevant",
    "data_integrity_relevant",
)


def _finding_questions(finding_id: str) -> list[JudgmentQuestion]:
    prompts = {
        "likely_valid": f"Does the supplied evidence suggest finding {finding_id} is likely valid?",
        "requirement_related": (
            f"Does the supplied evidence suggest finding {finding_id} relates to a stated requirement?"
        ),
        "requires_code_change": (
            f"Does the supplied evidence suggest finding {finding_id} requires a code change?"
        ),
        "requires_replan": (
            f"Does the supplied evidence suggest finding {finding_id} requires replanning the approach?"
        ),
        "likely_duplicate": (
            f"Does the supplied evidence suggest finding {finding_id} is a duplicate of another supplied finding?"
        ),
        "security_relevant": (
            f"Does the supplied evidence suggest finding {finding_id} is security-relevant? "
            "This is a triage signal, not a confirmation that a vulnerability exists."
        ),
        "data_integrity_relevant": (
            f"Does the supplied evidence suggest finding {finding_id} is relevant to data integrity?"
        ),
    }
    return [JudgmentQuestion(id=f"{finding_id}::{key}", question=text) for key, text in prompts.items()]


async def run_classify_findings(
    engine: Engine,
    *,
    task_goal: str,
    findings: list[Finding] | list[dict[str, Any]],
    requirements: list[Requirement] | list[dict[str, Any]] | None = None,
    client: ClientMeta | dict | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    parsed = [Finding.model_validate(item) for item in findings]
    reqs = [Requirement.model_validate(item) for item in (requirements or [])]
    client_meta = client_or_default(client)
    kept, find_warnings = enforce_count(parsed, engine.config.limits.max_findings, label="findings")
    reqs, req_warnings = enforce_count(reqs, engine.config.limits.max_requirements, label="requirements")
    questions: list[JudgmentQuestion] = []
    normalized = []
    for item in kept:
        normalized.append(
            {
                "id": item.id,
                "source": item.source,
                "text": normalize_text(item.text, strip_progress=False),
            }
        )
        questions.extend(_finding_questions(item.id))

    state = engine.attach_state_meta(
        {
            "task_goal": normalize_text(task_goal, strip_progress=False),
            "requirements": [
                {
                    "id": item.id,
                    "text": normalize_requirement_text(item.text, engine.config.limits.max_question_chars),
                }
                for item in reqs
            ],
            "findings": normalized,
        },
        LimitReport(),
    )
    result, cached, request_id = await engine.evaluate(
        tool=TOOL_NAME,
        tool_version=TOOL_VERSION,
        state=state,
        questions=questions,
        client=client_meta,
        use_cache=use_cache,
        original_chars=char_count(task_goal, parsed, reqs),
        warnings=find_warnings + req_warnings,
    )
    classified = []
    for item in normalized:
        signals = {key: result.answers[f"{item['id']}::{key}"] for key in SIGNAL_IDS}
        classified.append({"id": item["id"], "source": item.get("source"), "signals": signals})
    return engine.finalize(
        {
            "findings": classified,
            "note": "Signals are triage likelihoods. They do not confirm a defect or vulnerability.",
            "meta": engine.meta(result, cached=cached, request_id=request_id, tool=TOOL_NAME),
        },
        warnings=find_warnings + req_warnings,
    )
