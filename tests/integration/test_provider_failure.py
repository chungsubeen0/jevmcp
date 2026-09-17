import httpx

from jev_mcp.config import AppConfig
from jev_mcp.errors import ErrorCode, JevError
from jev_mcp.models import JudgmentQuestion
from jev_mcp.providers.typesafe import TypeSafeProvider
from jev_mcp.tools._common import safe_run


def _config(tmp_path, **provider_over) -> AppConfig:
    payload = {
        "name": "typesafe",
        "api_key": "test-key",
        "base_url": "https://api.typesafe.ai",
        "max_retries": 1,
        "timeout_seconds": 1,
    }
    payload.update(provider_over)
    return AppConfig.model_validate({"provider": payload, "data_dir": str(tmp_path)})


async def test_missing_key_is_structured():
    config = AppConfig.model_validate({"provider": {"name": "typesafe", "api_key": None}})
    provider = TypeSafeProvider(config)
    try:
        await provider.evaluate({"a": 1}, [JudgmentQuestion(id="Q1", question="X?")])
        raise AssertionError("expected error")
    except JevError as exc:
        assert exc.code == ErrorCode.PROVIDER_UNAVAILABLE
        dumped = json_secrets(exc)
        assert "Bearer" not in dumped
        assert "sk-" not in dumped


def json_secrets(exc: JevError) -> str:
    return str(exc.to_dict())


async def test_timeout_is_retryable(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    provider = TypeSafeProvider(
        _config(tmp_path),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        await provider.evaluate({"a": 1}, [JudgmentQuestion(id="Q1", question="X?")])
        raise AssertionError("expected timeout")
    except JevError as exc:
        assert exc.code == ErrorCode.PROVIDER_TIMEOUT
        assert exc.retryable is True
        assert "test-key" not in str(exc.to_dict())


async def test_rate_limit(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="slow down key=test-key")

    provider = TypeSafeProvider(
        _config(tmp_path, max_retries=0),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        await provider.evaluate({"a": 1}, [JudgmentQuestion(id="Q1", question="X?")])
        raise AssertionError("expected rate limit")
    except JevError as exc:
        assert exc.code == ErrorCode.PROVIDER_RATE_LIMITED
        dumped = exc.to_dict()
        assert "test-key" not in str(dumped)


async def test_safe_run_returns_error_payload():
    async def boom():
        raise JevError(ErrorCode.PROVIDER_UNAVAILABLE, "Jev evaluation unavailable.")

    payload = await safe_run(boom)
    assert payload["error"]["code"] == "PROVIDER_UNAVAILABLE"
    assert payload["error"]["retryable"] is True
