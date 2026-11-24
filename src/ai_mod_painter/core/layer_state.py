"""Per-layer view state: visible (eye) and red (mask)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayerState:
    key: str
    name: str
    visible: bool = True
    red: bool = False
