from __future__ import annotations

from jev_mcp.normalization.text import normalize_text
from jev_mcp.util.limits import LimitReport, apply_char_limit


def normalize_failure_output(output: str, max_chars: int) -> tuple[str, LimitReport]:
    cleaned = normalize_text(output)
    return apply_char_limit(cleaned, max_chars, label="failure output")
