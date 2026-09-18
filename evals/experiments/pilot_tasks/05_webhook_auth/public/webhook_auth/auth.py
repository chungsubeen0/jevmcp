"""Authenticate signed webhook requests."""

import hashlib
import hmac


def verify_webhook(
    secret: bytes,
    body: bytes,
    signature: str,
    timestamp: int,
    now: int,
    replay_window: int = 300,
) -> bool:
    signed = str(timestamp).encode("ascii") + b"." + body
    expected = "sha256=" + hmac.new(secret, signed, hashlib.sha256).hexdigest()
    return expected == signature
