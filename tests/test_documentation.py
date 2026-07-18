from __future__ import annotations

import unittest
from pathlib import Path


class DocumentationPrivacyTests(unittest.TestCase):
    def test_documentation_contains_no_user_home_paths(self) -> None:
        root = Path(__file__).resolve().parents[1]
        documentation = [root / "README.md", *sorted((root / "docs").rglob("*.md"))]
        forbidden = ("/Users/", "/home/", "C:\\Users\\")
        for path in documentation:
            text = path.read_text(encoding="utf-8")
            for prefix in forbidden:
                self.assertNotIn(prefix, text, f"private home path found in {path}")


if __name__ == "__main__":
    unittest.main()
