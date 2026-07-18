from __future__ import annotations

import re
from pathlib import Path

from ..model import Action, Manifest, MitmConfig, RewriteRule


_REDIRECT = re.compile(r"^(?P<pattern>\S+)\s+url\s+(?P<status>30[1278])\s+(?P<target>\S+)\s*$")
_REJECT = re.compile(r"^(?P<pattern>\S+)\s+url\s+(?P<kind>reject(?:-(?:200|dict|array|img))?)\s*$", re.I)
_SCRIPT = re.compile(
    r"^(?P<pattern>\S+)\s+url\s+script-(?P<side>request|response)-(?P<body>body|header)\s+(?P<script>\S+)\s*$",
    re.I,
)
_JSON_JQ_RESPONSE = re.compile(
    r"^(?P<pattern>\S+)\s+url\s+jsonjq-response-body\s+(?P<expression>.+?)\s*$",
    re.I,
)


def parse_file(path: Path) -> Manifest:
    return parse_text(path.read_text(encoding="utf-8-sig"), fallback_name=path.stem)


def parse_text(text: str, fallback_name: str = "Imported QX Rewrite") -> Manifest:
    section = ""
    name = fallback_name
    description = ""
    author = ""
    homepage = ""
    rewrites: list[RewriteRule] = []
    hostnames: list[str] = []
    warnings: list[str] = []

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("//") or line.startswith("#"):
            key, value = _metadata(line)
            if key in {"scriptname", "configname", "name"} and value:
                name = value
            elif key in {"description", "desc"} and value:
                description = value
            elif key == "author" and value:
                author = value
            elif key in {"homepage", "configurl"} and value:
                homepage = value
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue

        if section in {"rewrite_local", "rewrite", "url rewrite"} or (
            not section and _looks_like_rewrite(line)
        ):
            parsed = _parse_rewrite(line, number)
            if parsed is None:
                warnings.append(f"line {number}: unsupported rewrite syntax: {line}")
            else:
                rewrites.append(parsed)
        elif section == "mitm" or (not section and line.lower().startswith("hostname")):
            key, separator, value = line.partition("=")
            if separator and key.strip().lower() == "hostname":
                hostnames.extend(item.strip() for item in value.split(",") if item.strip())

    return Manifest(
        name=name,
        description=description,
        author=author,
        homepage=homepage,
        rewrites=rewrites,
        mitm=MitmConfig(hostnames=_deduplicate(hostnames)),
        warnings=warnings,
    )


def _parse_rewrite(line: str, number: int) -> RewriteRule | None:
    if match := _REDIRECT.match(line):
        return RewriteRule(
            pattern=match["pattern"],
            action=Action.REDIRECT,
            status=int(match["status"]),
            target=match["target"],
            source_line=number,
        )
    if match := _REJECT.match(line):
        return RewriteRule(
            pattern=match["pattern"],
            action=Action.REJECT,
            reject_type=match["kind"].lower(),
            source_line=number,
        )
    if match := _SCRIPT.match(line):
        side = match["side"].lower()
        body = match["body"].lower() == "body"
        return RewriteRule(
            pattern=match["pattern"],
            action=Action.SCRIPT_REQUEST if side == "request" else Action.SCRIPT_RESPONSE,
            script=match["script"],
            requires_body=body,
            source_line=number,
        )
    if match := _JSON_JQ_RESPONSE.match(line):
        return RewriteRule(
            pattern=match["pattern"],
            action=Action.JSON_JQ_RESPONSE,
            expression=match["expression"],
            requires_body=True,
            source_line=number,
        )
    return None


def _looks_like_rewrite(line: str) -> bool:
    return line.startswith(("^", "\\/", "(")) and " url " in line


def _metadata(line: str) -> tuple[str, str]:
    cleaned = line.lstrip("/# ")
    match = re.match(r"@?(?P<key>[A-Za-z]+)\s*[=:]?\s*(?P<value>.*)$", cleaned)
    if not match:
        return "", ""
    return match["key"].lower(), match["value"].strip()


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
