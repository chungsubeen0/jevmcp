import hashlib
import hmac
import unittest
from unittest import mock

from webhook_auth import verify_webhook


def sign(secret: bytes, body: bytes, timestamp: int) -> str:
    message = str(timestamp).encode("ascii") + b"." + body
    return "sha256=" + hmac.new(secret, message, hashlib.sha256).hexdigest()


class HiddenVerifyWebhookTests(unittest.TestCase):
    def test_uses_timing_safe_comparison(self) -> None:
        signature = sign(b"secret", b"body", 1_000)
        with mock.patch(
            "webhook_auth.auth.hmac.compare_digest",
            wraps=hmac.compare_digest,
        ) as compare:
            self.assertTrue(
                verify_webhook(b"secret", b"body", signature, 1_000, 1_000)
            )
        compare.assert_called_once()

    def test_replay_window_is_symmetric_and_inclusive(self) -> None:
        signature = sign(b"secret", b"body", 1_000)
        self.assertTrue(
            verify_webhook(b"secret", b"body", signature, 1_000, 1_300)
        )
        self.assertTrue(
            verify_webhook(b"secret", b"body", signature, 1_000, 700)
        )
        self.assertFalse(
            verify_webhook(b"secret", b"body", signature, 1_000, 1_301)
        )
        self.assertFalse(
            verify_webhook(b"secret", b"body", signature, 1_000, 699)
        )

    def test_malformed_signature_is_rejected(self) -> None:
        for signature in ("", "sha1=abc", "sha256=xyz", "sha256=00"):
            with self.subTest(signature=signature):
                self.assertFalse(
                    verify_webhook(b"secret", b"body", signature, 1_000, 1_000)
                )

    def test_negative_window_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            verify_webhook(b"secret", b"body", "sha256=00", 1_000, 1_000, -1)


if __name__ == "__main__":
    unittest.main()
