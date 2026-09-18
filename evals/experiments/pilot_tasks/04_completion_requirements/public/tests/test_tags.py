import unittest

from tag_tools import normalize_tags


class NormalizeTagsTests(unittest.TestCase):
    def test_trims_discards_blanks_and_normalizes(self) -> None:
        self.assertEqual(
            normalize_tags(["  Python ", "", " TESTING  "]),
            ["python", "testing"],
        )

    def test_accepts_generator(self) -> None:
        values = (value for value in [" One ", "Two"])
        self.assertEqual(normalize_tags(values), ["one", "two"])


if __name__ == "__main__":
    unittest.main()
