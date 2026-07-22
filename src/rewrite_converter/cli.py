from __future__ import annotations

import argparse
import json
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
) -> int:
    files = sorted(input_dir.rglob("*.conf"))
    if not files:
        raise ValueError(f"No .conf files found under {input_dir}")

    failed = False
    report: list[dict[str, object]] = []
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
            "generated": False,
        }
        if manifest.warnings or rule_errors or validation_warnings or manifest_errors:
            report.append(entry)

        for warning in manifest.warnings:
            level = "QUARANTINED" if quarantine_unsupported else "ERROR"
            print(f"{level}: {source}: {warning}", file=sys.stderr)
        for diagnostic in diagnostics:
            print(f"{source}: {diagnostic.render()}")

        has_unsupported = bool(manifest.warnings or rule_errors)
        if manifest_errors:
            failed = True
            continue
        if has_unsupported:
            if not quarantine_unsupported:
                failed = True
            print(f"SKIPPED: {source_relative} (file contains unsupported rules)")
            continue

        compatible_manifest = replace(manifest, warnings=[])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(get_emitter("loon")(compatible_manifest), encoding="utf-8")
        entry["generated"] = True
        print(f"WROTE: {destination}")

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 1 if failed else 0


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
