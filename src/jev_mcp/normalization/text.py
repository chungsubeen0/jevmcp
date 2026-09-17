from __future__ import annotations

import re

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\][^\x07]*\x07|\r")
PROGRESS_RE = re.compile(
    r"^.*(Downloading|Downloaded|Installing|Collecting|Progress|\d+%\|).*$",
    re.IGNORECASE | re.MULTILINE,
)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def strip_progress_noise(text: str) -> str:
    lines = []
    prev_progress = False
    for line in text.split("\n"):
        is_progress = bool(PROGRESS_RE.match(line.strip()))
        if is_progress and prev_progress:
            continue
        lines.append(line)
        prev_progress = is_progress
    return "\n".join(lines)


def collapse_duplicate_frames(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    seen_run: str | None = None
    repeats = 0
    for line in lines:
        if line.startswith("  File ") or line.strip().startswith("at "):
            if line == seen_run:
                repeats += 1
                continue
            if repeats > 2 and seen_run is not None:
                out.append(f"  … repeated {repeats} similar frames omitted")
            seen_run = line
            repeats = 0
        else:
            if repeats > 2 and seen_run is not None:
                out.append(f"  … repeated {repeats} similar frames omitted")
            seen_run = None
            repeats = 0
        out.append(line)
    return "\n".join(out)


def normalize_text(text: str, *, strip_progress: bool = True) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = strip_ansi(cleaned)
    cleaned = CONTROL_RE.sub("", cleaned)
    if strip_progress:
        cleaned = strip_progress_noise(cleaned)
    cleaned = collapse_duplicate_frames(cleaned)
    return cleaned.strip()
