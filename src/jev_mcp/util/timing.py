from __future__ import annotations

import time


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def elapsed_ms(started_ms: int) -> int:
    return max(0, monotonic_ms() - started_ms)
