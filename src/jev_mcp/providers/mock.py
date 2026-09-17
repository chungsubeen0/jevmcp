from __future__ import annotations

from collections.abc import Callable

from jev_mcp.models import JudgmentQuestion, JudgmentResult
from jev_mcp.util.hashing import sha256_text


class MockProvider:
    """Deterministic local provider. Used for tests, doctor dry-runs, and benchmarks."""

    name = "mock"

    def __init__(
        self,
        answers: dict[str, float] | None = None,
        default: float | None = None,
        resolver: Callable[[JudgmentQuestion, dict], float] | None = None,
        model: str = "mock-jev",
    ) -> None:
        self.answers = answers or {}
        self.default = default
        self.resolver = resolver
        self.model = model
        self.calls: list[tuple[dict, list[JudgmentQuestion]]] = []

    async def evaluate(
        self,
        state: dict,
        questions: list[JudgmentQuestion],
    ) -> JudgmentResult:
        self.calls.append((state, questions))
        resolved: dict[str, float] = {}
        for question in questions:
            if self.resolver is not None:
                value = self.resolver(question, state)
            elif question.id in self.answers:
                value = self.answers[question.id]
            elif self.default is not None:
                value = self.default
            else:
                digest = sha256_text(question.id + question.question)
                value = (int(digest[:8], 16) % 1000) / 1000.0
            resolved[question.id] = min(1.0, max(0.0, float(value)))
        return JudgmentResult(
            answers=resolved,
            provider=self.name,
            model=self.model,
            latency_ms=0,
            input_units=0,
        )

    async def close(self) -> None:
        return None


class MockJudgmentProvider(MockProvider):
    """Alias used by deterministic software tests. Never a stand-in for Jev intelligence."""
