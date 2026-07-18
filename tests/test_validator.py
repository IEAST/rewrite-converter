from __future__ import annotations

import unittest

from rewrite_converter.model import Action, Manifest, RewriteRule
from rewrite_converter.validator import validate


class ValidatorTests(unittest.TestCase):
    def test_rejects_invalid_redirect(self) -> None:
        manifest = Manifest(
            name="Bad",
            rewrites=[RewriteRule(pattern="(", action=Action.REDIRECT, status=200)],
        )
        diagnostics = validate(manifest)
        self.assertGreaterEqual(sum(item.level == "error" for item in diagnostics), 3)

    def test_warns_about_negative_loon_mitm_hostnames(self) -> None:
        manifest = Manifest(name="Demo")
        manifest.mitm.hostnames = ["-example.com"]
        diagnostics = validate(manifest, "loon")
        self.assertTrue(any("negative MITM" in item.message for item in diagnostics))


if __name__ == "__main__":
    unittest.main()

