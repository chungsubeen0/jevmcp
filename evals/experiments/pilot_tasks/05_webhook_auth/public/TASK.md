# Harden webhook authentication

Complete `webhook_auth.verify_webhook` using only the Python standard library.

Signatures use the form `sha256=<lowercase hex digest>`. The digest is HMAC
SHA-256 over:

```text
ASCII decimal timestamp + "." + raw request body
```

Requirements:

- calculate the expected digest with `hmac.new`;
- compare signatures with `hmac.compare_digest`, never `==`;
- return `False` for malformed signatures;
- accept timestamps exactly on the replay-window boundary;
- return `False` when the timestamp is older or farther in the future than
  `replay_window` seconds;
- raise `ValueError` for a negative replay window.

Keep the function deterministic by using the supplied `now` value. Do not
change its signature.
