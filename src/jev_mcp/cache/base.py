from __future__ import annotations

from typing import Any, Protocol


class JudgmentCache(Protocol):
    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def set(self, key: str, value: dict[str, Any], *, tool: str, provider: str, model: str) -> None: ...

    async def close(self) -> None: ...
