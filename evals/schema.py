from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Category = Literal[
    "compare_attempts",
    "triage_failure",
    "check_completion",
    "rank_context",
    "classify_findings",
    "assess_risk",
]


class Labels(BaseModel):
    expected_status: str | None = None
    expected_band: dict[str, Literal["LOW", "UNCERTAIN", "HIGH"]] = Field(default_factory=dict)
    expected_tiers: dict[str, Literal["HIGH", "MEDIUM", "LOW"]] = Field(default_factory=dict)
    critical_ids: list[str] = Field(default_factory=list)
    review_ids: list[str] = Field(default_factory=list)
    uncertain_expected: bool = False
    boolean_labels: dict[str, bool] = Field(default_factory=dict)
    notes: str = ""


class GoldenCase(BaseModel):
    id: str
    category: Category
    task: str
    input: dict[str, Any]
    labels: Labels
    mock_answers: dict[str, float] = Field(default_factory=dict)
    reviewed: bool = True
