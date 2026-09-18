import unittest

from command_bus import resolve


class RegistryTests(unittest.TestCase):
    def test_create_registration(self) -> None:
        self.assertEqual(resolve("create")("x"), "created:x")

    def test_preview_registration(self) -> None:
        self.assertEqual(resolve("preview")("x"), "preview:x")

    def test_unknown_command(self) -> None:
        with self.assertRaises(KeyError):
            resolve("missing")


if __name__ == "__main__":
    unittest.main()
