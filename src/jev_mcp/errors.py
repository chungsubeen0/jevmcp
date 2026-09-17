"""Structured MCP errors. Never include secrets or stack traces in client output."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    INVALID_PROVIDER_RESPONSE = "INVALID_PROVIDER_RESPONSE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


RETRYABLE_CODES = {
    ErrorCode.PROVIDER_UNAVAILABLE,
    ErrorCode.PROVIDER_TIMEOUT,
    ErrorCode.PROVIDER_RATE_LIMITED,
}


class JevError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = RETRYABLE_CODES.__contains__(code) if retryable is None else retryable
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        from jev_mcp.telemetry.privacy import redact_mapping, redact_text

        payload: dict[str, Any] = {
            "error": {
                "code": str(self.code),
                "message": redact_text(self.message),
                "retryable": self.retryable,
            }
        }
        if self.details:
            payload["error"]["details"] = redact_mapping(self.details)
        return payload


def sanitize_message(message: str, secrets: list[str] | None = None) -> str:
    from jev_mcp.telemetry.privacy import redact_text

    return redact_text(message, secrets)
