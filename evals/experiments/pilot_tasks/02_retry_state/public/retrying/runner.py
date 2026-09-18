"""Retry operations with a fixed attempt budget."""

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RetryableError(Exception):
    """An operation failure that may succeed on a later attempt."""


class RetryRunner:
    def __init__(self, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.max_attempts = max_attempts
        self._attempts = 0

    def run(self, operation: Callable[[], T]) -> T:
        while self._attempts < self.max_attempts:
            self._attempts += 1
            try:
                return operation()
            except RetryableError:
                if self._attempts == self.max_attempts:
                    raise
        raise RuntimeError("attempt budget exhausted")
