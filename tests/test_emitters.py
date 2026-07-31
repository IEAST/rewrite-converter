from __future__ import annotations

import unittest

from rewrite_converter.emitters.loon import emit as emit_loon
from rewrite_converter.emitters.quantumultx import emit as emit_qx
from rewrite_converter.emitters.shadowrocket import emit as emit_shadowrocket
from rewrite_converter.model import Action, Manifest, MitmConfig, RewriteRule


def example() -> Manifest:
    return Manifest(
        name="Demo",
        rewrites=[
            RewriteRule(
                pattern=r"^https?:\/\/google\.cn",
                action=Action.REDIRECT,
                status=302,
                target="https://www.google.com",
            ),
            RewriteRule(
                pattern=r"^https?:\/\/api\.example",
                action=Action.SCRIPT_RESPONSE,
                script="https://example.com/a.js",
                requires_body=True,
            ),
        ],
        mitm=MitmConfig(hostnames=["google.cn", "api.example"]),
    )


class EmitterTests(unittest.TestCase):
    def test_qx_output(self) -> None:
        output = emit_qx(example())
        self.assertIn("[rewrite_local]", output)
        self.assertIn("url 302 https://www.google.com", output)
        self.assertIn("script-response-body https://example.com/a.js", output)

    def test_loon_output(self) -> None:
        output = emit_loon(example())
        self.assertIn("[Rewrite]", output)
        self.assertNotIn("[URL Rewrite]", output)
        self.assertIn(" 302 https://www.google.com", output)
        self.assertIn("http-response ", output)
        self.assertIn("requires-body=true", output)

    def test_shadowrocket_output(self) -> None:
        output = emit_shadowrocket(example())
        self.assertIn("[URL Rewrite]", output)
        self.assertIn("https://www.google.com 302", output)
        self.assertIn("hostname = %APPEND% google.cn, api.example", output)


if __name__ == "__main__":
    unittest.main()
