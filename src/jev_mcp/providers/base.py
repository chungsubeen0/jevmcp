from __future__ import annotations

import os
from typing import Protocol

from jev_mcp.config import AppConfig
from jev_mcp.errors import ErrorCode, JevError
from jev_mcp.models import JudgmentQuestion, JudgmentResult


class JudgmentProvider(Protocol):
    name: str
    model: str

    async def evaluate(
        self,
        state: dict,
        questions: list[JudgmentQuestion],
    ) -> JudgmentResult: ...

    async def close(self) -> None: ...


def normalize_probability(value: object, question_id: str) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise JevError(
            ErrorCode.INVALID_PROVIDER_RESPONSE,
            f"Provider returned a non-numeric probability for {question_id}.",
            retryable=False,
        ) from exc
    if number != number:  # NaN
        raise JevError(
            ErrorCode.INVALID_PROVIDER_RESPONSE,
            f"Provider returned an invalid probability for {question_id}.",
            retryable=False,
        )
    return min(1.0, max(0.0, number))


def _faults_allowed() -> bool:
    return os.environ.get("JEV_MCP_ALLOW_FAULTS") == "1"


def build_provider(config: AppConfig, *, mock: JudgmentProvider | None = None) -> JudgmentProvider:
    if mock is not None:
        return mock
    fault = os.environ.get("JEV_MCP_TEST_FAULT")
    if fault and _faults_allowed():
        from jev_mcp.providers.fault import FaultProvider

        return FaultProvider(fault)
    if config.provider.name == "mock":
        from jev_mcp.providers.mock import MockProvider

        return MockProvider()
    from jev_mcp.providers.typesafe import TypeSafeProvider

    return TypeSafeProvider(config)
