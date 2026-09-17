from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from jev_mcp.cache.keys import cache_key
from jev_mcp.cache.sqlite import NullCache, SqliteCache
from jev_mcp.config import AppConfig
from jev_mcp.errors import ErrorCode, JevError
from jev_mcp.models import ClientMeta, InputMeta, JudgmentQuestion, JudgmentResult
from jev_mcp.policy.profiles import ProfilePolicy, resolve_profile
from jev_mcp.providers.base import JudgmentProvider
from jev_mcp.telemetry.events import CallEvent
from jev_mcp.telemetry.metrics import probability_summary
from jev_mcp.telemetry.privacy import hash_or_omit
from jev_mcp.telemetry.store import NullTelemetry, SqliteTelemetry
from jev_mcp.util.limits import LimitReport
from jev_mcp.util.timing import elapsed_ms, monotonic_ms


@dataclass
class Engine:
    config: AppConfig
    provider: JudgmentProvider
    cache: SqliteCache | NullCache
    telemetry: SqliteTelemetry | NullTelemetry
    profile: ProfilePolicy
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        config: AppConfig,
        *,
        provider: JudgmentProvider | None = None,
    ) -> Engine:
        from jev_mcp.cache.sqlite import build_cache
        from jev_mcp.providers.base import build_provider
        from jev_mcp.telemetry.store import build_telemetry

        return cls(
            config=config,
            provider=provider or build_provider(config),
            cache=build_cache(config),
            telemetry=build_telemetry(config),
            profile=resolve_profile(config),
        )

    def estimated_cost(self, input_units: int | None) -> float | None:
        price = self.config.cost.jev_input_per_million
        if price is None or input_units is None:
            return None
        return (input_units / 1_000_000) * price

    def attach_state_meta(self, state: dict[str, Any], report: LimitReport) -> dict[str, Any]:
        enriched = dict(state)
        if report.truncated or report.original_chars:
            enriched["_input_meta"] = InputMeta(
                truncated=report.truncated,
                original_chars=report.original_chars,
                submitted_chars=report.submitted_chars,
            ).model_dump()
        return enriched

    def validate_questions(self, questions: list[JudgmentQuestion]) -> None:
        limits = self.config.limits
        if not questions:
            raise JevError(ErrorCode.INVALID_INPUT, "At least one question is required.")
        if len(questions) > limits.max_question_count:
            raise JevError(
                ErrorCode.INPUT_TOO_LARGE,
                f"Question count {len(questions)} exceeds limit {limits.max_question_count}.",
            )
        seen: set[str] = set()
        for question in questions:
            if not question.id or not question.question.strip():
                raise JevError(ErrorCode.INVALID_INPUT, "Each question needs an id and text.")
            if question.id in seen:
                raise JevError(ErrorCode.INVALID_INPUT, f"Duplicate question id: {question.id}")
            seen.add(question.id)
            if len(question.question) > limits.max_question_chars:
                raise JevError(
                    ErrorCode.INPUT_TOO_LARGE,
                    f"Question {question.id} exceeds {limits.max_question_chars} characters.",
                )

    async def evaluate(
        self,
        *,
        tool: str,
        tool_version: str,
        state: dict[str, Any],
        questions: list[JudgmentQuestion],
        client: ClientMeta | None = None,
        use_cache: bool = True,
        cacheable: bool = True,
        original_chars: int = 0,
        warnings: list[str] | None = None,
    ) -> tuple[JudgmentResult, bool, str]:
        self.validate_questions(questions)
        request_id = str(uuid.uuid4())
        client_meta = client or ClientMeta()
        started = monotonic_ms()
        cacheable = cacheable and use_cache and self.config.cache.enabled
        key = cache_key(
            provider=self.provider.name,
            model=self.provider.model,
            tool=tool,
            tool_version=tool_version,
            state=state,
            questions=questions,
        )

        cached_hit = False
        result: JudgmentResult | None = None
        status = "ok"
        error_code: str | None = None
        try:
            if cacheable:
                cached = await self.cache.get(key)
                if cached is not None:
                    result = JudgmentResult.model_validate(cached)
                    cached_hit = True
            if result is None:
                result = await self.provider.evaluate(state, questions)
                if cacheable:
                    await self.cache.set(
                        key,
                        result.model_dump(),
                        tool=tool,
                        provider=result.provider,
                        model=result.model,
                    )
            return result, cached_hit, request_id
        except JevError as exc:
            status = "error"
            error_code = str(exc.code)
            raise
        except Exception as exc:
            status = "error"
            error_code = str(ErrorCode.INTERNAL_ERROR)
            raise JevError(ErrorCode.INTERNAL_ERROR, "Internal Jev MCP error.") from exc
        finally:
            latency = elapsed_ms(started)
            answers = result.answers if result is not None else {}
            event = CallEvent(
                timestamp=time.time(),
                request_id=request_id,
                session_id=client_meta.session_id,
                task_id=client_meta.task_id,
                client=client_meta.name,
                mode=str(client_meta.mode),
                model_if_known=client_meta.model,
                tool=tool,
                provider=self.provider.name,
                provider_model=self.provider.model,
                input_chars=original_chars,
                normalized_chars=len(str(state)),
                question_count=len(questions),
                cache_hit=cached_hit,
                latency_ms=latency,
                status=status,
                probability_summary=probability_summary(answers),
                error_code=error_code,
                state_hash=hash_or_omit(state, store_hashes=self.config.telemetry.store_hashes),
                questions_hash=hash_or_omit(
                    [q.model_dump() for q in questions],
                    store_hashes=self.config.telemetry.store_hashes,
                ),
                jev_input_units=result.input_units if result else None,
                jev_estimated_cost=self.estimated_cost(result.input_units) if result else None,
                estimated_frontier_context_chars=original_chars or None,
                content={"state": state, "warnings": warnings} if self.config.telemetry.store_content else None,
            )
            await self.telemetry.record(event)

    def meta(
        self,
        result: JudgmentResult,
        *,
        cached: bool,
        request_id: str,
        tool: str,
        extra_latency_ms: int = 0,
    ) -> dict[str, Any]:
        return {
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms + extra_latency_ms,
            "cached": cached,
            "request_id": request_id,
            "tool": tool,
            "shadow_mode": self.config.server.shadow_mode,
            "jev_input_units": result.input_units,
            "jev_estimated_cost": self.estimated_cost(result.input_units),
        }

    def finalize(
        self,
        payload: dict[str, Any],
        *,
        warnings: list[str],
    ) -> dict[str, Any]:
        out = dict(payload)
        if warnings:
            out["warnings"] = warnings
        if self.config.server.shadow_mode:
            out["advisory"] = (
                "Shadow mode is enabled. Treat this as telemetry, not a mandatory control action."
            )
        forbidden = {"APPROVED", "CORRECT", "SAFE_TO_MERGE", "SECURE"}
        status = str(out.get("status", ""))
        if status in forbidden:
            raise JevError(ErrorCode.INTERNAL_ERROR, "Illegal completion status produced.")
        return out

    async def close(self) -> None:
        await self.cache.close()
        await self.telemetry.close()
        await self.provider.close()
