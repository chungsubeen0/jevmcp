import unittest

from command_bus import resolve
from command_bus.handlers import archive


class HiddenRegistryTests(unittest.TestCase):
    def test_archive_resolves_to_archive_handler(self) -> None:
        self.assertIs(resolve("archive"), archive)
        self.assertEqual(resolve("archive")("x"), "archived:x")


if __name__ == "__main__":
    unittest.main()
