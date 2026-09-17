"""Shared request, response, and provider models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClientMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "unknown"
    mode: Literal["autonomous", "interactive", "custom"] | str = "interactive"
    model: str | None = None
    client_version: str | None = None
    session_id: str | None = None
    task_id: str | None = None


class Requirement(StrictModel):
    id: str
    text: str


class Finding(StrictModel):
    id: str
    text: str
    source: str | None = None


class ContextCandidate(StrictModel):
    id: str
    path: str | None = None
    symbol: str | None = None
    content: str = ""


class Attempt(StrictModel):
    hypothesis: str = ""
    approach: str = ""
    changed_files: list[str] = Field(default_factory=list)
    diff_summary: str = ""
    failure: str = ""


class FailureEvent(StrictModel):
    command: str = ""
    exit_code: int | None = None
    summary: str = ""
    output: str = ""


class PreviousFailure(StrictModel):
    summary: str = ""
    output: str | None = None


class TaskInput(StrictModel):
    goal: str
    requirements: list[Requirement] = Field(default_factory=list)


class ImplementationInput(StrictModel):
    changed_files: list[str] = Field(default_factory=list)
    diff_summary: str = ""


class VerificationInput(StrictModel):
    tests: str = ""
    lint: str = ""
    typecheck: str = ""
    other: list[str] = Field(default_factory=list)


class JudgeQuestion(StrictModel):
    id: str
    question: str


class JudgmentQuestion(BaseModel):
    """Provider-facing question. One proposition, evidence-grounded."""

    model_config = ConfigDict(extra="ignore")

    id: str
    question: str
    criteria: dict[str, str] | None = None


class InputMeta(BaseModel):
    truncated: bool = False
    original_chars: int = 0
    submitted_chars: int = 0


class CallMeta(BaseModel):
    provider: str
    model: str
    latency_ms: int
    cached: bool = False
    request_id: str | None = None
    tool: str | None = None
    shadow_mode: bool = False
    jev_input_units: int | None = None
    jev_estimated_cost: float | None = None


class JudgmentResult(BaseModel):
    answers: dict[str, float]
    provider: str
    model: str
    latency_ms: int = 0
    input_units: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ProbabilityBands(BaseModel):
    low: float = 0.30
    high: float = 0.70

    @field_validator("low", "high")
    @classmethod
    def _unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("threshold must be in [0, 1]")
        return value


class StuckThresholds(BaseModel):
    same_failure: float = 0.85
    same_strategy: float = 0.80
    max_new_evidence: float = 0.30
    max_progress: float = 0.30


class OutcomeFeedback(StrictModel):
    request_id: str
    decision_useful: bool | None = None
    eventual_classification: str | None = None
    task_succeeded: bool | None = None
    notes: str | None = None
