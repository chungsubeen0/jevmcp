from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlparse

import httpx

from jev_mcp.config import AppConfig
from jev_mcp.errors import ErrorCode, JevError, sanitize_message
from jev_mcp.models import JudgmentQuestion, JudgmentResult
from jev_mcp.providers.base import normalize_probability
from jev_mcp.util.timing import elapsed_ms, monotonic_ms

TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504, 529}
DEFAULT_ALLOWED_HOSTS = {"api.typesafe.ai"}


def allowed_typesafe_hosts() -> set[str]:
    extra = os.environ.get("TYPESAFE_ALLOWED_HOSTS", "")
    hosts = set(DEFAULT_ALLOWED_HOSTS)
    hosts.update(item.strip() for item in extra.split(",") if item.strip())
    return hosts


def assert_safe_base_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise JevError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "TypeSafe base URL must use HTTPS.",
            retryable=False,
        )
    host = (parsed.hostname or "").lower()
    if host not in allowed_typesafe_hosts():
        raise JevError(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "TypeSafe base URL host is not allowed.",
            retryable=False,
        )


class TypeSafeProvider:
    """System One HTTP provider. Client is created lazily on first evaluate()."""

    name = "typesafe"

    def __init__(
        self,
        config: AppConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self.model = config.provider.model
        self._client = client
        self._owns_client = client is None

    def _secrets(self) -> list[str]:
        key = self._config.provider.api_key
        return [key] if key else []

    async def _client_or_create(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._config.provider.timeout_seconds,
                follow_redirects=False,
            )
        return self._client

    def _questions_payload(self, questions: list[JudgmentQuestion]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for question in questions:
            entry: dict[str, Any] = {"type": "noul", "instructions": question.question}
            if question.criteria:
                entry["criteria"] = question.criteria
            payload[question.id] = entry
        return payload

    def _map_status(self, status_code: int, body_text: str) -> JevError:
        message = sanitize_message(body_text, self._secrets())
        if status_code in {401, 403}:
            return JevError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "TypeSafe rejected the request. Check TYPESAFE_API_KEY.",
                retryable=False,
            )
        if status_code == 429:
            return JevError(ErrorCode.PROVIDER_RATE_LIMITED, "TypeSafe rate-limited the request.")
        if status_code == 529:
            return JevError(ErrorCode.PROVIDER_UNAVAILABLE, "TypeSafe is temporarily overloaded.")
        if status_code >= 500:
            return JevError(ErrorCode.PROVIDER_UNAVAILABLE, "TypeSafe is temporarily unavailable.")
        return JevError(
            ErrorCode.INVALID_PROVIDER_RESPONSE,
            f"TypeSafe returned HTTP {status_code}.",
            retryable=False,
            details={"body": message[:300]},
        )

    async def _request(self, payload: dict[str, Any]) -> httpx.Response:
        client = await self._client_or_create()
        url = self._config.provider.base_url.rstrip("/") + "/v1/systemone"
        headers = {
            "Authorization": f"Bearer {self._config.provider.api_key}",
            "Content-Type": "application/json",
        }
        attempts = 1 + max(0, self._config.provider.max_retries)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2)
                    continue
                raise JevError(ErrorCode.PROVIDER_TIMEOUT, "Jev evaluation timed out.") from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.2)
                    continue
                raise JevError(
                    ErrorCode.PROVIDER_UNAVAILABLE,
                    "Unable to reach TypeSafe.",
                ) from exc

            if response.status_code in TRANSIENT_STATUS and attempt + 1 < attempts:
                await asyncio.sleep(0.2)
                continue
            return response

        raise JevError(ErrorCode.PROVIDER_UNAVAILABLE, "Unable to reach TypeSafe.") from last_error

    def _parse_answers(
        self, data: dict[str, Any], questions: list[JudgmentQuestion]
    ) -> dict[str, float]:
        answers = data.get("answers")
        if not isinstance(answers, dict):
            raise JevError(
                ErrorCode.INVALID_PROVIDER_RESPONSE,
                "TypeSafe response did not include answers.",
                retryable=False,
            )
        resolved: dict[str, float] = {}
        for question in questions:
            item = answers.get(question.id)
            if not isinstance(item, dict) or "noul" not in item:
                raise JevError(
                    ErrorCode.INVALID_PROVIDER_RESPONSE,
                    f"TypeSafe response missing noul for {question.id}.",
                    retryable=False,
                )
            resolved[question.id] = normalize_probability(item["noul"], question.id)
        return resolved

    async def evaluate(
        self,
        state: dict,
        questions: list[JudgmentQuestion],
    ) -> JudgmentResult:
        if not self._config.provider.api_key:
            raise JevError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "TYPESAFE_API_KEY is not configured.",
                retryable=False,
            )
        assert_safe_base_url(self._config.provider.base_url)
        payload = {
            "state": state,
            "model": self.model,
            "questions": self._questions_payload(questions),
        }
        started = monotonic_ms()
        response = await self._request(payload)
        latency = elapsed_ms(started)
        if response.status_code >= 400:
            raise self._map_status(response.status_code, response.text)
        try:
            data = response.json()
        except ValueError as exc:
            raise JevError(
                ErrorCode.INVALID_PROVIDER_RESPONSE,
                "TypeSafe returned invalid JSON.",
                retryable=False,
            ) from exc
        if not isinstance(data, dict):
            raise JevError(
                ErrorCode.INVALID_PROVIDER_RESPONSE,
                "TypeSafe returned an unexpected payload.",
                retryable=False,
            )
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return JudgmentResult(
            answers=self._parse_answers(data, questions),
            provider=self.name,
            model=str(data.get("model") or self.model),
            latency_ms=latency,
            input_units=usage.get("input_tokens"),
            raw={"usage": usage},
        )

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
