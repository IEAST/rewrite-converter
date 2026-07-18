from __future__ import annotations

import re
from dataclasses import dataclass

from .model import Action, Manifest, RewriteRule


@dataclass(frozen=True)
class Diagnostic:
    level: str
    message: str
    rule_index: int | None = None

    def render(self) -> str:
        location = f"rule[{self.rule_index}]: " if self.rule_index is not None else ""
        return f"{self.level.upper()}: {location}{self.message}"


def validate(manifest: Manifest, target: str | None = None) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if not manifest.name.strip():
        diagnostics.append(Diagnostic("error", "manifest name cannot be empty"))

    seen: set[tuple[object, ...]] = set()
    for index, rule in enumerate(manifest.rewrites):
        diagnostics.extend(_validate_rule(rule, index, target))
        signature = (
            rule.pattern,
            rule.action,
            rule.status,
            rule.target,
            rule.reject_type,
            rule.script,
            rule.expression,
        )
        if signature in seen:
            diagnostics.append(Diagnostic("warning", "duplicate rewrite rule", index))
        seen.add(signature)

    positive_hosts = {h for h in manifest.mitm.hostnames if not h.startswith("-")}
    for host in sorted(positive_hosts):
        if "://" in host or "/" in host:
            diagnostics.append(Diagnostic("error", f"invalid MITM hostname: {host}"))

    if target == "loon":
        excluded = [h for h in manifest.mitm.hostnames if h.startswith("-")]
        if excluded:
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "negative MITM hostnames require manual verification in Loon: "
                    + ", ".join(excluded),
                )
            )
    return diagnostics


def _validate_rule(rule: RewriteRule, index: int, target: str | None) -> list[Diagnostic]:
    result: list[Diagnostic] = []
    try:
        re.compile(rule.pattern)
    except re.error as exc:
        result.append(Diagnostic("error", f"invalid regular expression: {exc}", index))

    if rule.action == Action.REDIRECT:
        if rule.status not in {301, 302, 307, 308}:
            result.append(Diagnostic("error", "redirect status must be 301, 302, 307 or 308", index))
        if not rule.target:
            result.append(Diagnostic("error", "redirect requires target", index))
    elif rule.action == Action.REJECT:
        if not rule.reject_type:
            result.append(Diagnostic("error", "reject requires reject_type", index))
    elif rule.action in {Action.SCRIPT_REQUEST, Action.SCRIPT_RESPONSE}:
        if not rule.script:
            result.append(Diagnostic("error", "script action requires script URL/path", index))
    elif rule.action == Action.JSON_JQ_RESPONSE:
        if not rule.expression:
            result.append(Diagnostic("error", "JSON JQ response action requires expression", index))
        if target == "shadowrocket":
            result.append(
                Diagnostic(
                    "error",
                    "JSON JQ response rewrite has no verified Shadowrocket equivalent",
                    index,
                )
            )

    if target == "loon" and rule.action == Action.REDIRECT and rule.status in {301, 308}:
        result.append(
            Diagnostic(
                "warning",
                f"Loon redirect status {rule.status} should be verified on the installed app version",
                index,
            )
        )
    return result
