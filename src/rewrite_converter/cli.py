from __future__ import annotations

import argparse
import sys
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
