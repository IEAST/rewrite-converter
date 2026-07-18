from __future__ import annotations

import json
from pathlib import Path

from .model import Manifest


def load_manifest(path: Path) -> Manifest:
    """Load the canonical JSON manifest.

    JSON is deliberately used as the first canonical format: it is in Python's
    standard library, has an unambiguous grammar, and can be validated without
    adding a dependency. YAML can be added later as an input adapter.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Manifest root must be a JSON object")
    return Manifest.from_dict(value)


def save_manifest(manifest: Manifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

