from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

from .emitters import get_emitter
from .manifest import load_manifest, save_manifest
from .parsers.quantumultx import parse_file
from .validator import validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rewrite-converter",
        description="Parse, validate and generate mobile proxy rewrite configurations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    import_qx = sub.add_parser("import-qx", help="convert a QX rewrite config to canonical JSON")
    import_qx.add_argument("input", type=Path)
    import_qx.add_argument("-o", "--output", type=Path, required=True)

    import_tree = sub.add_parser("import-qx-tree", help="import every QX .conf under a directory")
    import_tree.add_argument("input", type=Path)
    import_tree.add_argument("-o", "--output-dir", type=Path, required=True)

    publish_loon = sub.add_parser(
        "generate-loon-tree",
        help="import a tree of QX configs and generate a matching tree of Loon plugins",
    )
    publish_loon.add_argument("input", type=Path)
    publish_loon.add_argument("-o", "--output-dir", type=Path, required=True)
    publish_loon.add_argument(
        "--quarantine-unsupported",
        action="store_true",
        help="skip files containing unsupported rules and record them instead of failing",
    )
    publish_loon.add_argument("--report", type=Path, help="write a JSON compatibility report")
    publish_loon.add_argument(
        "--allowlist",
        type=Path,
        help="JSON mapping source paths to approved compatibility fingerprints",
    )

    generate = sub.add_parser("generate", help="generate a client configuration from JSON")
    generate.add_argument("input", type=Path)
    generate.add_argument("--target", required=True, choices=["qx", "loon", "shadowrocket"])
    generate.add_argument("-o", "--output", type=Path, required=True)

    batch = sub.add_parser("generate-all", help="generate all supported client formats")
    batch.add_argument("input", type=Path)
    batch.add_argument("-o", "--output-dir", type=Path, required=True)

    check = sub.add_parser("validate", help="validate a canonical manifest")
    check.add_argument("input", type=Path)
    check.add_argument("--target", choices=["qx", "loon", "shadowrocket"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "import-qx":
            manifest = parse_file(args.input)
            save_manifest(manifest, args.output)
            _print_import_warnings(manifest.warnings)
            return 0
        if args.command == "import-qx-tree":
            files = sorted(args.input.rglob("*.conf"))
            if not files:
                raise ValueError(f"No .conf files found under {args.input}")
            warning_count = 0
            for source in files:
                manifest = parse_file(source)
                relative = source.relative_to(args.input).with_suffix(".json")
                destination = args.output_dir / relative
                save_manifest(manifest, destination)
                warning_count += len(manifest.warnings)
                print(f"IMPORTED: {source} -> {destination} ({len(manifest.warnings)} warnings)")
            print(f"SUMMARY: {len(files)} files, {warning_count} unsupported lines")
            return 0
        if args.command == "generate-loon-tree":
            return _generate_loon_tree(
                args.input,
                args.output_dir,
                quarantine_unsupported=args.quarantine_unsupported,
                report_path=args.report,
                allowlist_path=args.allowlist,
            )
        if args.command == "generate":
            manifest = load_manifest(args.input)
            return _generate(manifest, args.target, args.output)
        if args.command == "generate-all":
            manifest = load_manifest(args.input)
            args.output_dir.mkdir(parents=True, exist_ok=True)
            statuses = [
                _generate(manifest, target, args.output_dir / f"{_slug(manifest.name)}.{_extension(target)}")
                for target in ("qx", "loon", "shadowrocket")
            ]
            return max(statuses)
        if args.command == "validate":
            manifest = load_manifest(args.input)
            diagnostics = validate(manifest, args.target)
            for diagnostic in diagnostics:
                print(diagnostic.render())
            return 1 if any(item.level == "error" for item in diagnostics) else 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    raise AssertionError("unreachable")


def _generate(manifest, target: str, output: Path) -> int:
    diagnostics = validate(manifest, target)
    for diagnostic in diagnostics:
        print(diagnostic.render())
    if any(item.level == "error" for item in diagnostics):
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(get_emitter(target)(manifest), encoding="utf-8")
    print(f"WROTE: {output}")
    return 0


def _generate_loon_tree(
    input_dir: Path,
    output_dir: Path,
    *,
    quarantine_unsupported: bool = False,
    report_path: Path | None = None,
    allowlist_path: Path | None = None,
) -> int:
    files = sorted(input_dir.rglob("*.conf"))
    if not files:
        raise ValueError(f"No .conf files found under {input_dir}")

    failed = False
    report: list[dict[str, object]] = []
    allowlist = _load_allowlist(allowlist_path)
    for source in files:
        source_relative = source.relative_to(input_dir)
        manifest = parse_file(source)
        destination = output_dir / source_relative.with_suffix(".plugin")

        diagnostics = validate(manifest, "loon")
        rule_errors = {
            item.rule_index
            for item in diagnostics
            if item.level == "error" and item.rule_index is not None
        }
        manifest_errors = [
            item for item in diagnostics if item.level == "error" and item.rule_index is None
        ]
        validation_warnings = [item for item in diagnostics if item.level == "warning"]
        blocking_issues = [
            _parser_issue(warning) for warning in manifest.warnings
        ] + [
            _rule_issue(manifest, diagnostics, index) for index in sorted(rule_errors)
        ]
        approved_fingerprints = allowlist.get(source_relative.as_posix(), set())
        all_blocking_issues_approved = bool(blocking_issues) and all(
            issue["fingerprint"] in approved_fingerprints for issue in blocking_issues
        )
        for issue in blocking_issues:
            issue["allowed"] = issue["fingerprint"] in approved_fingerprints

        entry: dict[str, object] = {
            "source": source_relative.as_posix(),
            "parser_warnings": list(manifest.warnings),
            "dropped_rules": [
                {
                    "rule_index": index,
                    "source_line": manifest.rewrites[index].source_line,
                    "diagnostics": [
                        item.message
                        for item in diagnostics
                        if item.level == "error" and item.rule_index == index
                    ],
                }
                for index in sorted(rule_errors)
            ],
            "manifest_errors": [item.message for item in manifest_errors],
            "validation_warnings": [item.message for item in validation_warnings],
            "blocking_issues": blocking_issues,
            "allowlisted": all_blocking_issues_approved,
            "generated": False,
        }
        if manifest.warnings or rule_errors or validation_warnings or manifest_errors:
            report.append(entry)

        for warning in manifest.warnings:
            if all_blocking_issues_approved:
                level = "ALLOWLISTED"
            else:
                level = "QUARANTINED" if quarantine_unsupported else "ERROR"
            print(f"{level}: {source}: {warning}", file=sys.stderr)
        for diagnostic in diagnostics:
            print(f"{source}: {diagnostic.render()}")

        has_unsupported = bool(manifest.warnings or rule_errors)
        if manifest_errors:
            failed = True
            continue
        if has_unsupported:
            if not all_blocking_issues_approved:
                if not quarantine_unsupported:
                    failed = True
                print(f"SKIPPED: {source_relative} (file contains unapproved rules)")
                continue

        compatible_manifest = replace(
            manifest,
            rewrites=[
                rule for index, rule in enumerate(manifest.rewrites) if index not in rule_errors
            ],
            warnings=[],
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        output = get_emitter("loon")(compatible_manifest)
        if all_blocking_issues_approved:
            output = (
                "# WARNING: compatibility exceptions were manually approved; "
                "see _compatibility.json.\n" + output
            )
        destination.write_text(output, encoding="utf-8")
        entry["generated"] = True
        print(f"WROTE: {destination}")

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 1 if failed else 0


def _load_allowlist(path: Path | None) -> dict[str, set[str]]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Compatibility allowlist root must be a JSON object")
    result: dict[str, set[str]] = {}
    for source, fingerprints in value.items():
        if not isinstance(source, str) or not isinstance(fingerprints, list) or not all(
            isinstance(item, str) for item in fingerprints
        ):
            raise ValueError("Compatibility allowlist must map source paths to string lists")
        result[source] = set(fingerprints)
    return result


def _parser_issue(warning: str) -> dict[str, object]:
    match = re.match(r"line (?P<line>\d+): (?P<message>.*)", warning)
    source_line = int(match["line"]) if match else None
    message = match["message"] if match else warning
    return {
        "kind": "parser_warning",
        "source_line": source_line,
        "message": message,
        "fingerprint": _fingerprint("parser_warning", message),
    }


def _rule_issue(manifest, diagnostics, index: int) -> dict[str, object]:
    messages = sorted(
        item.message
        for item in diagnostics
        if item.level == "error" and item.rule_index == index
    )
    rule = manifest.rewrites[index]
    identity = json.dumps(
        {
            "pattern": rule.pattern,
            "action": rule.action.value,
            "messages": messages,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return {
        "kind": "rule_error",
        "source_line": rule.source_line,
        "message": "; ".join(messages),
        "fingerprint": _fingerprint("rule_error", identity),
    }


def _fingerprint(kind: str, value: str) -> str:
    digest = hashlib.sha256(f"{kind}\0{value}".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _print_import_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"WARNING: {warning}")


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "rewrite"


def _extension(target: str) -> str:
    return {"qx": "conf", "loon": "plugin", "shadowrocket": "module"}[target]


if __name__ == "__main__":
    raise SystemExit(main())
