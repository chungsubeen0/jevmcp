import unittest

from retrying import RetryableError, RetryRunner


class RetryRunnerTests(unittest.TestCase):
    def test_retries_until_success(self) -> None:
        calls = 0

        def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RetryableError("temporary")
            return "ok"

        self.assertEqual(RetryRunner(3).run(operation), "ok")
        self.assertEqual(calls, 3)

    def test_unrelated_error_is_not_retried(self) -> None:
        runner = RetryRunner(3)
        with self.assertRaises(KeyError):
            runner.run(lambda: {}["missing"])


if __name__ == "__main__":
    unittest.main()
