from __future__ import annotations

from typing import Any

from jev_mcp.engine import Engine
from jev_mcp.models import ClientMeta, JudgmentQuestion, Requirement
from jev_mcp.normalization.diffs import normalize_diff
from jev_mcp.normalization.requirements import normalize_requirement_text
from jev_mcp.normalization.text import normalize_text
from jev_mcp.policy.decisions import risk_review_warranted
from jev_mcp.tools._common import char_count, client_or_default
from jev_mcp.util.limits import LimitReport, enforce_count

TOOL_NAME = "jev_assess_risk"
TOOL_VERSION = "1.0.0"
DESCRIPTION = (
    "Cheap change-risk triage to decide whether a more expensive frontier review appears warranted. "
    "Returns sensitivity likelihoods only. These are not security conclusions and do not certify safety."
)

SIGNAL_QUESTIONS = {
    "security_sensitive": "Does the supplied evidence suggest the change is security-sensitive?",
    "authentication_sensitive": "Does the supplied evidence suggest the change is authentication-sensitive?",
    "authorization_sensitive": "Does the supplied evidence suggest the change is authorization-sensitive?",
    "data_integrity_sensitive": "Does the supplied evidence suggest the change is data-integrity-sensitive?",
    "schema_sensitive": "Does the supplied evidence suggest the change is schema-sensitive?",
    "public_api_sensitive": "Does the supplied evidence suggest the change is public-API-sensitive?",
    "architecture_sensitive": "Does the supplied evidence suggest the change is architecture-sensitive?",
    "payment_sensitive": "Does the supplied evidence suggest the change is payment-sensitive?",
    "broad_regression_risk": "Does the supplied evidence suggest the change carries broad regression risk?",
}

QUESTIONS = [
    JudgmentQuestion(
        id=key,
        question=text + " This is a triage signal, not a security or correctness conclusion.",
    )
    for key, text in SIGNAL_QUESTIONS.items()
]


async def run_assess_risk(
    engine: Engine,
    *,
    task_goal: str,
    changed_files: list[str] | None = None,
    diff_summary: str = "",
    requirements: list[Requirement] | list[dict[str, Any]] | None = None,
    client: ClientMeta | dict | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    reqs = [Requirement.model_validate(item) for item in (requirements or [])]
    client_meta = client_or_default(client)
    reqs, req_warnings = enforce_count(reqs, engine.config.limits.max_requirements, label="requirements")
    diff, diff_report = normalize_diff(diff_summary, engine.config.limits.max_state_chars // 2)
    report = LimitReport().merge(diff_report)
    state = engine.attach_state_meta(
        {
            "task_goal": normalize_text(task_goal, strip_progress=False),
            "changed_files": changed_files or [],
            "diff_summary": diff,
            "requirements": [
                {
                    "id": item.id,
                    "text": normalize_requirement_text(item.text, engine.config.limits.max_question_chars),
                }
                for item in reqs
            ],
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
        original_chars=char_count(task_goal, changed_files, diff_summary, reqs),
        warnings=report.warnings + req_warnings,
    )
    return engine.finalize(
        {
            "signals": result.answers,
            "further_frontier_review_warranted": risk_review_warranted(
                result.answers, engine.config.thresholds.default
            ),
            "note": "Triage signals only. Not a security conclusion.",
            "meta": engine.meta(result, cached=cached, request_id=request_id, tool=TOOL_NAME),
        },
        warnings=report.warnings + req_warnings,
    )
