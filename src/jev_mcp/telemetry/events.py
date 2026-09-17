from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CallEvent(BaseModel):
    timestamp: float
    request_id: str
    session_id: str | None = None
    task_id: str | None = None
    client: str | None = None
    mode: str | None = None
    model_if_known: str | None = None
    tool: str
    provider: str
    provider_model: str
    input_chars: int = 0
    normalized_chars: int = 0
    question_count: int = 0
    cache_hit: bool = False
    latency_ms: int = 0
    status: str = "ok"
    probability_summary: dict[str, float] = Field(default_factory=dict)
    error_code: str | None = None
    state_hash: str | None = None
    questions_hash: str | None = None
    jev_input_units: int | None = None
    jev_estimated_cost: float | None = None
    estimated_frontier_context_chars: int | None = None
    content: dict[str, Any] | None = None
