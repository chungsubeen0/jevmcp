from __future__ import annotations

import logging
import re
from typing import Any

from jev_mcp.util.hashing import sha256_json

SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "token",
    "password",
    "secret",
    "access_token",
    "refresh_token",
}

SECRET_PATTERNS = [
    re.compile(r"apikey_[A-Za-z0-9_]+", re.IGNORECASE),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"glpat-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"npm_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:aws)?_?secret_?access_?key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{30,}", re.IGNORECASE),
    re.compile(r"sk_(?:live|test)_[A-Za-z0-9]+"),
    re.compile(r"rk_(?:live|test)_[A-Za-z0-9]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?:postgres(?:ql)?|mysql|mongodb|redis)://[^\s'\"\\]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(
        r"(?:TYPESAFE_API_KEY|AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID|GH_TOKEN|GITHUB_TOKEN|NPM_TOKEN)="
        r"[^\s]+"
    ),
]


def redact_text(text: str, extra_secrets: list[str] | None = None) -> str:
    cleaned = text
    for secret in extra_secrets or []:
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def redact_mapping(value: Any, extra_secrets: list[str] | None = None) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS or "secret" in str(key).lower():
                out[key] = "[REDACTED]"
            else:
                out[key] = redact_mapping(item, extra_secrets)
        return out
    if isinstance(value, list):
        return [redact_mapping(item, extra_secrets) for item in value]
    if isinstance(value, str):
        return redact_text(value, extra_secrets)
    return value


def hash_or_omit(value: Any, *, store_hashes: bool) -> str | None:
    if not store_hashes:
        return None
    return sha256_json(redact_mapping(value))


class SecretLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {key: redact_text(str(val)) for key, val in record.args.items()}
            else:
                record.args = tuple(
                    redact_text(str(arg)) if not isinstance(arg, int | float) else arg for arg in record.args
                )
        return True
