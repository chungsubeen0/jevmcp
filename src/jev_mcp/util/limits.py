from __future__ import annotations

from dataclasses import dataclass, field

from jev_mcp.errors import ErrorCode, JevError


@dataclass
class LimitReport:
    truncated: bool = False
    original_chars: int = 0
    submitted_chars: int = 0
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: LimitReport) -> LimitReport:
        return LimitReport(
            truncated=self.truncated or other.truncated,
            original_chars=self.original_chars + other.original_chars,
            submitted_chars=self.submitted_chars + other.submitted_chars,
            warnings=[*self.warnings, *other.warnings],
        )


def apply_char_limit(text: str, max_chars: int, *, label: str = "input") -> tuple[str, LimitReport]:
    original = len(text)
    if original <= max_chars:
        return text, LimitReport(original_chars=original, submitted_chars=original)

    if max_chars < 32:
        clipped = text[:max_chars]
    else:
        head = int(max_chars * 0.60)
        tail = max_chars - head - 16
        if tail < 8:
            clipped = text[:max_chars]
        else:
            marker = "\n…[truncated]…\n"
            clipped = text[:head] + marker + text[-tail:]
            if len(clipped) > max_chars:
                clipped = clipped[:max_chars]

    report = LimitReport(
        truncated=True,
        original_chars=original,
        submitted_chars=len(clipped),
        warnings=[f"{label} was truncated before evaluation."],
    )
    return clipped, report


def enforce_count(items: list, max_count: int, *, label: str) -> tuple[list, list[str]]:
    if len(items) <= max_count:
        return items, []
    if max_count <= 0:
        raise JevError(
            ErrorCode.INPUT_TOO_LARGE,
            f"{label} exceeds configured limits.",
            retryable=False,
        )
    return items[:max_count], [f"{label} count exceeded {max_count}; extra items were dropped."]
