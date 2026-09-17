from __future__ import annotations

from typing import Any

from jev_mcp import NORMALIZATION_VERSION, POLICY_VERSION
from jev_mcp.models import JudgmentQuestion
from jev_mcp.util.hashing import sha256_json


def cache_key(
    *,
    provider: str,
    model: str,
    tool: str,
    tool_version: str,
    state: dict[str, Any],
    questions: list[JudgmentQuestion],
    policy_version: str = POLICY_VERSION,
    normalization_version: str = NORMALIZATION_VERSION,
) -> str:
    payload = {
        "provider": provider,
        "model": model,
        "tool": tool,
        "tool_version": tool_version,
        "policy_version": policy_version,
        "normalization_version": normalization_version,
        "state": state,
        "questions": [q.model_dump(exclude_none=True) for q in questions],
    }
    return sha256_json(payload)
