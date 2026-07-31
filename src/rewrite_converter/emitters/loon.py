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
    lines = metadata_comments(manifest)
    rewrite_lines: list[str] = []
    script_lines: list[str] = []
    for index, rule in enumerate(manifest.rewrites):
        if not rule.enabled:
            continue
        if rule.action in {Action.SCRIPT_REQUEST, Action.SCRIPT_RESPONSE}:
            script_lines.append(_script(manifest, rule, index))
        else:
            rewrite_lines.append(_rewrite(rule))

    lines.extend(["", "[Rewrite]"])
    lines.extend(rewrite_lines)
    lines.extend(["", "[Script]"])
    lines.extend(script_lines)
    lines.extend(["", "[MITM]"])
    if manifest.mitm.hostnames:
        lines.append("hostname = " + ",".join(manifest.mitm.hostnames))
    return "\n".join(lines).rstrip() + "\n"


def _rewrite(rule: RewriteRule) -> str:
    if rule.action == Action.REDIRECT:
        return f"{rule.pattern} {rule.status} {rule.target}"
    if rule.action == Action.REJECT:
        return f"{rule.pattern} {_REJECT_MAP[rule.reject_type or 'reject']}"
    if rule.action == Action.JSON_JQ_RESPONSE:
        return f"{rule.pattern} response-body-json-jq {rule.expression}"
    raise AssertionError(f"not a Loon URL rewrite: {rule.action}")


def _script(manifest: Manifest, rule: RewriteRule, index: int) -> str:
    side = "http-request" if rule.action == Action.SCRIPT_REQUEST else "http-response"
    options = [
        f"script-path={rule.script}",
        f"tag={tag_for(manifest, index, rule.tag)}",
        f"timeout={rule.timeout}",
    ]
    if rule.requires_body:
        options.append("requires-body=true")
    options.append("enable=true")
    return f"{side} {rule.pattern} " + ",".join(options)
