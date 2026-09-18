import hashlib
import hmac
import unittest

from webhook_auth import verify_webhook


def sign(secret: bytes, body: bytes, timestamp: int) -> str:
    message = str(timestamp).encode("ascii") + b"." + body
    return "sha256=" + hmac.new(secret, message, hashlib.sha256).hexdigest()


class VerifyWebhookTests(unittest.TestCase):
    def test_accepts_valid_signature(self) -> None:
        signature = sign(b"secret", b'{"ok":true}', 1_000)
        self.assertTrue(
            verify_webhook(b"secret", b'{"ok":true}', signature, 1_000, 1_010)
        )

    def test_rejects_tampered_body(self) -> None:
        signature = sign(b"secret", b"original", 1_000)
        self.assertFalse(
            verify_webhook(b"secret", b"changed", signature, 1_000, 1_010)
        )


if __name__ == "__main__":
    unittest.main()
