"""Test-only fault injection. Requires JEV_MCP_ALLOW_FAULTS=1 plus JEV_MCP_TEST_FAULT."""

from __future__ import annotations

from jev_mcp.errors import ErrorCode, JevError
from jev_mcp.models import JudgmentQuestion, JudgmentResult


class FaultProvider:
    name = "fault"

    def __init__(self, mode: str, model: str = "fault-jev") -> None:
        self.mode = mode
        self.model = model

    async def evaluate(self, state: dict, questions: list[JudgmentQuestion]) -> JudgmentResult:
        if self.mode == "timeout":
            raise JevError(ErrorCode.PROVIDER_TIMEOUT, "Jev evaluation timed out.")
        if self.mode == "unavailable":
            raise JevError(ErrorCode.PROVIDER_UNAVAILABLE, "Jev evaluation unavailable.")
        if self.mode == "rate_limited":
            raise JevError(ErrorCode.PROVIDER_RATE_LIMITED, "TypeSafe rate-limited the request.")
        if self.mode == "malformed":
            raise JevError(
                ErrorCode.INVALID_PROVIDER_RESPONSE,
                "TypeSafe response missing noul for Q1.",
                retryable=False,
            )
        raise JevError(ErrorCode.INTERNAL_ERROR, f"Unknown test fault: {self.mode}")

    async def close(self) -> None:
        return None
