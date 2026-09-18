# Reset retry state between runs

`retrying.RetryRunner` correctly retries one operation, but reusing the same
runner for another operation can skip attempts.

Make each call to `run` receive its own full `max_attempts` budget. Preserve
these behaviors:

- return immediately after a successful attempt;
- retry only `RetryableError`;
- re-raise the final `RetryableError` when the budget is exhausted;
- let unrelated exceptions propagate immediately.

Do not change the public constructor or `run` signature.
