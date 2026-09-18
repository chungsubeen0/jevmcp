import unittest

from retrying import RetryableError, RetryRunner


class HiddenRetryRunnerTests(unittest.TestCase):
    def test_reused_runner_gets_fresh_attempt_budget(self) -> None:
        runner = RetryRunner(2)
        self.assertEqual(runner.run(lambda: "first"), "first")
        calls = 0

        def second() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RetryableError("try again")
            return "second"

        self.assertEqual(runner.run(second), "second")
        self.assertEqual(calls, 2)

    def test_each_exhausted_run_uses_full_budget(self) -> None:
        runner = RetryRunner(2)
        calls = 0

        def fail() -> None:
            nonlocal calls
            calls += 1
            raise RetryableError("still failing")

        for _ in range(2):
            with self.assertRaises(RetryableError):
                runner.run(fail)
        self.assertEqual(calls, 4)


if __name__ == "__main__":
    unittest.main()
