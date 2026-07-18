from __future__ import annotations

import unittest

from rewrite_converter.model import Action
from rewrite_converter.parsers.quantumultx import parse_text


class QuantumultXParserTests(unittest.TestCase):
    def test_parses_redirect_reject_scripts_and_mitm(self) -> None:
        manifest = parse_text(
            r"""
// @ScriptName Demo
// @Author Alice
[rewrite_local]
^https?:\/\/google\.cn url 302 https://www.google.com
^https?:\/\/ads\.example url reject-200
^https?:\/\/api\.example url script-response-body https://example.com/a.js
^https?:\/\/request\.example url script-request-header https://example.com/b.js
[mitm]
hostname = google.cn, api.example
"""
        )
        self.assertEqual("Demo", manifest.name)
        self.assertEqual("Alice", manifest.author)
        self.assertEqual(4, len(manifest.rewrites))
        self.assertEqual(Action.REDIRECT, manifest.rewrites[0].action)
        self.assertEqual(Action.REJECT, manifest.rewrites[1].action)
        self.assertEqual(Action.SCRIPT_RESPONSE, manifest.rewrites[2].action)
        self.assertTrue(manifest.rewrites[2].requires_body)
        self.assertEqual(Action.SCRIPT_REQUEST, manifest.rewrites[3].action)
        self.assertFalse(manifest.rewrites[3].requires_body)
        self.assertEqual(["google.cn", "api.example"], manifest.mitm.hostnames)
        self.assertEqual([], manifest.warnings)

    def test_unknown_rewrite_is_preserved_as_warning(self) -> None:
        manifest = parse_text("[rewrite_local]\n^x url request-header add Foo Bar")
        self.assertEqual([], manifest.rewrites)
        self.assertEqual(1, len(manifest.warnings))

    def test_parses_flat_qx_snippet_without_sections(self) -> None:
        manifest = parse_text(
            "hostname = www.google.cn\n"
            r"^https?:\/\/google\.cn url 302 https://www.google.com"
        )
        self.assertEqual(1, len(manifest.rewrites))
        self.assertEqual(["www.google.cn"], manifest.mitm.hostnames)

    def test_parses_json_jq_response(self) -> None:
        manifest = parse_text(
            r"^https?:\/\/api\.example url jsonjq-response-body 'del(.ads)'"
        )
        self.assertEqual(Action.JSON_JQ_RESPONSE, manifest.rewrites[0].action)
        self.assertEqual("'del(.ads)'", manifest.rewrites[0].expression)


if __name__ == "__main__":
    unittest.main()
