"""HTTP bind guards and static bearer gate. Token never logged."""

from __future__ import annotations

import hmac
from collections.abc import Iterable

from jev_mcp.config import LOOPBACK_HOSTS, AppConfig
from jev_mcp.errors import ErrorCode, JevError


class HttpBindError(JevError):
    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.INVALID_INPUT, message, retryable=False)


def is_loopback(host: str) -> bool:
    return host.strip().lower() in LOOPBACK_HOSTS


def assert_http_ready(config: AppConfig) -> None:
    """Refuse unsafe HTTP listen settings before opening a socket."""
    http = config.server.http
    host = http.host.strip()
    loopback = is_loopback(host)
    has_token = bool(http.token)

    if not loopback and not http.bind_all:
        raise HttpBindError("Non-loopback HTTP bind requires JEV_MCP_HTTP_BIND_ALL=1 and a token.")
    if not loopback and not has_token:
        raise HttpBindError("Non-loopback HTTP bind requires JEV_MCP_HTTP_TOKEN.")
    if http.require_token and not has_token and not http.allow_anon:
        raise HttpBindError("HTTP transport requires JEV_MCP_HTTP_TOKEN (or JEV_MCP_HTTP_ALLOW_ANON=1 for tests).")
    if http.allow_anon and not loopback:
        raise HttpBindError("Anonymous HTTP is only allowed on loopback.")


def bearer_matches(authorization: str | None, token: str) -> bool:
    if not authorization or not token:
        return False
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return False
    return hmac.compare_digest(value.encode("utf-8"), token.encode("utf-8"))


class BearerGate:
    """ASGI wrapper. /health stays public. /mcp requires Bearer when a token is set."""

    def __init__(self, app, token: str | None, *, public_paths: Iterable[str] = ("/health",)) -> None:
        self.app = app
        self.token = token
        self.public_paths = frozenset(public_paths)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self.token is None:
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if path in self.public_paths:
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        if bearer_matches(headers.get("authorization"), self.token):
            await self.app(scope, receive, send)
            return
        body = b'{"error":{"code":"UNAUTHORIZED","message":"Missing or invalid bearer token.","retryable":false}}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
