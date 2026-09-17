from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from jev_mcp.config import AppConfig
from jev_mcp.models import OutcomeFeedback
from jev_mcp.telemetry.events import CallEvent
from jev_mcp.telemetry.privacy import redact_mapping
from jev_mcp.util.files import secure_data_file


class NullTelemetry:
    async def record(self, event: CallEvent) -> None:
        return None

    async def record_outcome(self, outcome: OutcomeFeedback) -> None:
        return None

    def export_rows(self) -> list[dict[str, Any]]:
        return []

    async def close(self) -> None:
        return None


class SqliteTelemetry:
    def __init__(self, path: Path, *, store_content: bool) -> None:
        self.path = path
        self.store_content = store_content
        self._lock = asyncio.Lock()
        secure_data_file(path)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                request_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outcomes (
                request_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        secure_data_file(path)

    async def record(self, event: CallEvent) -> None:
        payload = redact_mapping(event.model_dump())
        if not self.store_content:
            payload["content"] = None
        async with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO events (request_id, timestamp, payload) VALUES (?, ?, ?)",
                (event.request_id, event.timestamp, json.dumps(payload)),
            )
            self._conn.commit()

    async def record_outcome(self, outcome: OutcomeFeedback) -> None:
        async with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO outcomes (request_id, timestamp, payload) VALUES (?, ?, ?)",
                (outcome.request_id, time.time(), json.dumps(outcome.model_dump())),
            )
            self._conn.commit()

    def export_rows(self) -> list[dict[str, Any]]:
        events = {
            row["request_id"]: json.loads(row["payload"])
            for row in self._conn.execute("SELECT request_id, payload FROM events")
        }
        for row in self._conn.execute("SELECT request_id, payload FROM outcomes"):
            payload = events.get(row["request_id"], {"request_id": row["request_id"]})
            payload["outcome"] = json.loads(row["payload"])
            events[row["request_id"]] = payload
        return list(events.values())

    async def close(self) -> None:
        async with self._lock:
            self._conn.close()


def build_telemetry(config: AppConfig) -> SqliteTelemetry | NullTelemetry:
    if not config.telemetry.enabled:
        return NullTelemetry()
    return SqliteTelemetry(config.telemetry_path(), store_content=config.telemetry.store_content)
