from __future__ import annotations

from ..model import Action, Manifest, RewriteRule
from .common import metadata_comments


def emit(manifest: Manifest) -> str:
    lines = metadata_comments(manifest)
    lines.extend(["", "[rewrite_local]"])
    lines.extend(_rule(rule) for rule in manifest.rewrites if rule.enabled)
    lines.extend(["", "[mitm]"])
    if manifest.mitm.hostnames:
        lines.append("hostname = " + ", ".join(manifest.mitm.hostnames))
    return "\n".join(lines).rstrip() + "\n"


def _rule(rule: RewriteRule) -> str:
    if rule.action == Action.REDIRECT:
        return f"{rule.pattern} url {rule.status} {rule.target}"
    if rule.action == Action.REJECT:
        return f"{rule.pattern} url {rule.reject_type}"
    if rule.action == Action.SCRIPT_REQUEST:
        part = "body" if rule.requires_body else "header"
        return f"{rule.pattern} url script-request-{part} {rule.script}"
    if rule.action == Action.SCRIPT_RESPONSE:
        part = "body" if rule.requires_body else "header"
        return f"{rule.pattern} url script-response-{part} {rule.script}"
    if rule.action == Action.JSON_JQ_RESPONSE:
        return f"{rule.pattern} url jsonjq-response-body {rule.expression}"
    raise AssertionError(f"unhandled action: {rule.action}")
