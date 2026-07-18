from __future__ import annotations

from collections.abc import Callable

from ..model import Manifest
from .loon import emit as emit_loon
from .quantumultx import emit as emit_quantumultx
from .shadowrocket import emit as emit_shadowrocket

Emitter = Callable[[Manifest], str]

EMITTERS: dict[str, Emitter] = {
    "qx": emit_quantumultx,
    "quantumultx": emit_quantumultx,
    "loon": emit_loon,
    "shadowrocket": emit_shadowrocket,
    "sr": emit_shadowrocket,
}


def get_emitter(target: str) -> Emitter:
    try:
        return EMITTERS[target.lower()]
    except KeyError as exc:
        choices = ", ".join(sorted(EMITTERS))
        raise ValueError(f"Unknown target {target!r}; choose one of: {choices}") from exc

