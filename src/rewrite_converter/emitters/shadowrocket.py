from __future__ import annotations

from ..model import Action, Manifest, RewriteRule
from .common import metadata_comments, tag_for


_REJECT_MAP = {
    "reject": "reject",
    "reject-200": "reject-200",
    "reject-dict": "reject-dict",
    "reject-array": "reject-array",
    "reject-img": "reject-img",
}


def emit(manifest: Manifest) -> str:
    """Emit a Shadowrocket module-style configuration.

    Shadowrocket shares the Surge-style section layout for these portable
    rewrite/script operations. Target validation still reports semantics that
    cannot be proven equivalent.
    """
    lines = metadata_comments(manifest)
    rewrites: list[str] = []
    scripts: list[str] = []
    for index, rule in enumerate(manifest.rewrites):
        if not rule.enabled:
            continue
        if rule.action in {Action.SCRIPT_REQUEST, Action.SCRIPT_RESPONSE}:
            scripts.append(_script(manifest, rule, index))
        elif rule.action == Action.JSON_JQ_RESPONSE:
            rewrites.append(f"# UNSUPPORTED JSON-JQ: {rule.pattern} {rule.expression}")
        else:
            rewrites.append(_rewrite(rule))

    lines.extend(["", "[URL Rewrite]", *rewrites])
    lines.extend(["", "[Script]", *scripts])
    lines.extend(["", "[MITM]"])
    if manifest.mitm.hostnames:
        lines.append("hostname = %APPEND% " + ", ".join(manifest.mitm.hostnames))
    return "\n".join(lines).rstrip() + "\n"


def _rewrite(rule: RewriteRule) -> str:
    if rule.action == Action.REDIRECT:
        return f"{rule.pattern} {rule.target} {rule.status}"
    if rule.action == Action.REJECT:
        return f"{rule.pattern} - {_REJECT_MAP[rule.reject_type or 'reject']}"
    raise AssertionError(f"not a Shadowrocket URL rewrite: {rule.action}")


def _script(manifest: Manifest, rule: RewriteRule, index: int) -> str:
    side = "http-request" if rule.action == Action.SCRIPT_REQUEST else "http-response"
    options = [
        f"script-path={rule.script}",
        f"timeout={rule.timeout}",
        f"tag={tag_for(manifest, index, rule.tag)}",
    ]
    if rule.requires_body:
        options.append("requires-body=true")
    return f"{side} {rule.pattern} " + ",".join(options)
