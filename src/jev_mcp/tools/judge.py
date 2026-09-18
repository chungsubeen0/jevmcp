from __future__ import annotations

import re
from typing import Any

from jev_mcp.engine import Engine
from jev_mcp.errors import ErrorCode, JevError
from jev_mcp.models import ClientMeta, JudgeQuestion, JudgmentQuestion
from jev_mcp.normalization.text import normalize_text
from jev_mcp.tools._common import char_count, client_or_default
from jev_mcp.util.limits import apply_char_limit

TOOL_NAME = "jev_judge"
TOOL_VERSION = "1.0.0"
DESCRIPTION = (
    "Generic bounded judgment primitive. During implementation, ask one evidence-grounded "
    "yes/no proposition about progress toward a predefined goal so the user can decide the "
    "next attempt. Rejects generative requests and product/planning decisions (code, "
    "architecture, roadmaps, market/pricing choices). Does not invent a plan or write the work."
)

GENERATIVE_RE = re.compile(
    r"(?i)"
    r"^\s*(write|design|fix|generate|implement|create|draft|rewrite|code|refactor)\b"
    r"|write this function"
    r"|design this architecture"
    r"|fix this bug"
    r"|generate tests"
    r"|write documentation"
    r"|implement the"
    r"|produce (the )?(code|patch|diff|tests|docs)"
    r"|write (a |the )?(plan|roadmap|sprint|backlog|business case)"
    r"|draft (a |the )?(plan|roadmap|sprint|business)"
    r"|create (a |the )?(plan|roadmap|backlog)"
)

DECISION_RE = re.compile(
    r"(?i)"
    r"\b(should we|shall we|what should we|which (plan|option|strategy|architecture))\b"
    r"|\b(choose|pick|decide) (between|the|a|which)\b"
    r"|\bprioritize\b.+\bover\b"
    r"|\benter the\b.+\bmarket\b"
    r"|\b(go-to-market|pricing (model|strategy)|business strategy)\b"
)


def reject_generative(question: str) -> None:
    if GENERATIVE_RE.search(question) or DECISION_RE.search(question):
        raise JevError(
            ErrorCode.INVALID_INPUT,
            "jev_judge rejects generative work and product or planning decisions. "
            "Ask one evidence-grounded proposition instead.",
            retryable=False,
        )


async def run_judge(
    engine: Engine,
    *,
    state: dict[str, Any],
    questions: list[JudgeQuestion] | list[dict[str, Any]],
    client: ClientMeta | dict | None = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    parsed = [JudgeQuestion.model_validate(item) for item in questions]
    client_meta = client_or_default(client)
    for item in parsed:
        reject_generative(item.question)

    serialized = normalize_text(str(state), strip_progress=False)
    clipped, report = apply_char_limit(
        serialized, engine.config.limits.max_state_chars, label="state"
    )
    provider_state = engine.attach_state_meta({"state": clipped}, report)
    provider_questions = [
        JudgmentQuestion(id=item.id, question=normalize_text(item.question, strip_progress=False))
        for item in parsed
    ]
    result, cached, request_id = await engine.evaluate(
        tool=TOOL_NAME,
        tool_version=TOOL_VERSION,
        state=provider_state,
        questions=provider_questions,
        client=client_meta,
        use_cache=use_cache,
        original_chars=char_count(state, parsed),
        warnings=report.warnings,
    )
    return engine.finalize(
        {
            "answers": result.answers,
            "meta": engine.meta(result, cached=cached, request_id=request_id, tool=TOOL_NAME),
        },
        warnings=report.warnings,
    )
