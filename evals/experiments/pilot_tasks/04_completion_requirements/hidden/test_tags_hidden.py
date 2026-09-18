import ast
import unittest
from pathlib import Path

from tag_tools import normalize_tags


class HiddenNormalizeTagsTests(unittest.TestCase):
    def test_deduplicates_and_preserves_order(self) -> None:
        self.assertEqual(
            normalize_tags([" Beta ", "ALPHA", "beta", "alpha", "Gamma"]),
            ["beta", "alpha", "gamma"],
        )

    def test_raises_instead_of_truncating(self) -> None:
        with self.assertRaises(ValueError):
            normalize_tags(["one", "two", "three"], max_tags=2)

    def test_non_positive_limits_are_rejected(self) -> None:
        for limit in (0, -1):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                normalize_tags([], max_tags=limit)

    def test_requested_visible_regressions_were_added(self) -> None:
        fixture_root = Path(__file__).parents[1]
        test_file = fixture_root / "tests" / "test_tags.py"
        if not test_file.exists():
            test_file = fixture_root / "public" / "tests" / "test_tags.py"
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
        method_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn("test_deduplicates_case_insensitively", method_names)
        self.assertIn("test_rejects_non_positive_limit", method_names)


if __name__ == "__main__":
    unittest.main()
