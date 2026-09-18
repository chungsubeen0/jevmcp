"""Normalize user-supplied tags."""

from collections.abc import Iterable


def normalize_tags(values: Iterable[str], max_tags: int = 5) -> list[str]:
    result = []
    for value in values:
        cleaned = value.strip()
        if cleaned:
            result.append(cleaned)
    return result[:max_tags]
