from __future__ import annotations

import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from rewrite_converter.cli import main
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

    def test_generate_loon_tree_preserves_relative_paths(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "inputs" / "nested" / "demo.conf"
            source.parent.mkdir(parents=True)
            source.write_text("^https://example\\.com url reject-200\n", encoding="utf-8")

            with redirect_stdout(StringIO()):
                status = main(["generate-loon-tree", str(root / "inputs"), "-o", str(root / "output")])

            self.assertEqual(0, status)
            plugin = root / "output" / "nested" / "demo.plugin"
            self.assertTrue(plugin.exists())
            output = plugin.read_text(encoding="utf-8")
            self.assertIn("[Rewrite]", output)
            self.assertNotIn("[URL Rewrite]", output)

    def test_generate_loon_tree_rejects_unsupported_lines(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "inputs" / "bad.conf"
            source.parent.mkdir(parents=True)
            source.write_text("^https://example\\.com url request-header add Foo Bar\n", encoding="utf-8")

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                status = main(["generate-loon-tree", str(root / "inputs"), "-o", str(root / "output")])

            self.assertEqual(1, status)
            self.assertFalse((root / "output" / "bad.plugin").exists())

    def test_generate_loon_tree_quarantines_entire_unsupported_file(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "inputs" / "nested" / "mixed.conf"
            source.parent.mkdir(parents=True)
            source.write_text("^good url reject-200\n^bad url unsupported\n", encoding="utf-8")
            report = root / "report.json"

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                status = main(
                    [
                        "generate-loon-tree",
                        str(root / "inputs"),
                        "-o",
                        str(root / "output"),
                        "--quarantine-unsupported",
                        "--report",
                        str(report),
                    ]
                )

            self.assertEqual(0, status)
            plugin = root / "output" / "nested" / "mixed.plugin"
            self.assertFalse(plugin.exists())
            self.assertIn("unsupported rewrite syntax", report.read_text(encoding="utf-8"))
            self.assertIn('"generated": false', report.read_text(encoding="utf-8"))

    def test_generate_loon_tree_publishes_only_exactly_allowlisted_issues(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "inputs" / "nested" / "mixed.conf"
            source.parent.mkdir(parents=True)
            source.write_text("^good url reject-200\n^bad url unsupported\n", encoding="utf-8")
            first_report = root / "first-report.json"

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                main(
                    [
                        "generate-loon-tree",
                        str(root / "inputs"),
                        "-o",
                        str(root / "first-output"),
                        "--quarantine-unsupported",
                        "--report",
                        str(first_report),
                    ]
                )
            fingerprint = json.loads(first_report.read_text(encoding="utf-8"))[0][
                "blocking_issues"
            ][0]["fingerprint"]
            allowlist = root / "allowlist.json"
            allowlist.write_text(
                json.dumps({"nested/mixed.conf": [fingerprint]}),
                encoding="utf-8",
            )
            second_report = root / "second-report.json"

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                status = main(
                    [
                        "generate-loon-tree",
                        str(root / "inputs"),
                        "-o",
                        str(root / "second-output"),
                        "--quarantine-unsupported",
                        "--allowlist",
                        str(allowlist),
                        "--report",
                        str(second_report),
                    ]
                )

            self.assertEqual(0, status)
            plugin = root / "second-output" / "nested" / "mixed.plugin"
            output = plugin.read_text(encoding="utf-8")
            self.assertIn("compatibility exceptions were manually approved", output)
            self.assertIn("^good reject-200", output)
            self.assertNotIn("^bad", output)
            self.assertTrue(json.loads(second_report.read_text(encoding="utf-8"))[0]["allowlisted"])

            source.write_text(
                "^good url reject-200\n^bad url unsupported\n^new url unsupported-too\n",
                encoding="utf-8",
            )
            third_report = root / "third-report.json"
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                status = main(
                    [
                        "generate-loon-tree",
                        str(root / "inputs"),
                        "-o",
                        str(root / "third-output"),
                        "--quarantine-unsupported",
                        "--allowlist",
                        str(allowlist),
                        "--report",
                        str(third_report),
                    ]
                )

            self.assertEqual(0, status)
            self.assertFalse((root / "third-output" / "nested" / "mixed.plugin").exists())
            self.assertFalse(json.loads(third_report.read_text(encoding="utf-8"))[0]["allowlisted"])


if __name__ == "__main__":
    unittest.main()
