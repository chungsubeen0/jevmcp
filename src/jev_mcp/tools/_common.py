from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from jev_mcp.engine import Engine
from jev_mcp.errors import ErrorCode, JevError
from jev_mcp.models import ClientMeta


def client_or_default(client: ClientMeta | dict | None) -> ClientMeta | None:
    if client is None:
        return None
    if isinstance(client, ClientMeta):
        return client
    return ClientMeta.model_validate(client)


async def safe_run(fn: Callable[[], Awaitable[dict[str, Any]]]) -> dict[str, Any]:
    try:
        return await fn()
    except JevError as exc:
        return exc.to_dict()
    except Exception:
        return JevError(ErrorCode.INTERNAL_ERROR, "Internal Jev MCP error.").to_dict()


def char_count(*parts: object) -> int:
    return sum(len(str(part)) for part in parts if part is not None)


def engine_profile(engine: Engine, client: ClientMeta | None):
    # Client metadata is telemetry only. Profile comes from server config.
    _ = client
    return engine.profile
