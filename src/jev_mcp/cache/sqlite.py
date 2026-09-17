from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from jev_mcp.config import AppConfig
from jev_mcp.util.files import secure_data_file


class NullCache:
    async def get(self, key: str) -> dict[str, Any] | None:
        return None

    async def set(
        self, key: str, value: dict[str, Any], *, tool: str, provider: str, model: str
    ) -> None:
        return None

    async def close(self) -> None:
        return None


class SqliteCache:
    def __init__(self, path: Path, *, ttl_seconds: int, max_entries: int) -> None:
        self.path = path
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._lock = asyncio.Lock()
        secure_data_file(path)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS judgments (
                key TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                tool TEXT NOT NULL,
                response TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        secure_data_file(path)

    def _purge_locked(self) -> None:
        now = int(time.time())
        self._conn.execute("DELETE FROM judgments WHERE expires_at <= ?", (now,))
        count = self._conn.execute("SELECT COUNT(*) FROM judgments").fetchone()[0]
        if count > self.max_entries:
            overflow = count - self.max_entries
            self._conn.execute(
                """
                DELETE FROM judgments WHERE key IN (
                    SELECT key FROM judgments ORDER BY created_at ASC LIMIT ?
                )
                """,
                (overflow,),
            )
        self._conn.commit()

    async def get(self, key: str) -> dict[str, Any] | None:
        async with self._lock:
            now = int(time.time())
            row = self._conn.execute(
                "SELECT response, expires_at FROM judgments WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            response, expires_at = row
            if expires_at <= now:
                self._conn.execute("DELETE FROM judgments WHERE key = ?", (key,))
                self._conn.commit()
                return None
            return json.loads(response)

    async def set(
        self, key: str, value: dict[str, Any], *, tool: str, provider: str, model: str
    ) -> None:
        async with self._lock:
            now = int(time.time())
            self._conn.execute(
                """
                INSERT OR REPLACE INTO judgments
                (key, created_at, expires_at, provider, model, tool, response)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    now,
                    now + self.ttl_seconds,
                    provider,
                    model,
                    tool,
                    json.dumps(value),
                ),
            )
            self._purge_locked()

    async def close(self) -> None:
        async with self._lock:
            self._conn.close()


def build_cache(config: AppConfig) -> SqliteCache | NullCache:
    if not config.cache.enabled:
        return NullCache()
    return SqliteCache(
        config.cache_path(),
        ttl_seconds=config.cache.ttl_seconds,
        max_entries=config.cache.max_entries,
    )
