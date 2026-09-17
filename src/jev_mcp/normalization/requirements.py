from __future__ import annotations

from jev_mcp.normalization.text import normalize_text
from jev_mcp.util.limits import apply_char_limit


def normalize_requirement_text(text: str, max_chars: int) -> str:
    cleaned, _ = apply_char_limit(normalize_text(text, strip_progress=False), max_chars, label="requirement")
    return cleaned
