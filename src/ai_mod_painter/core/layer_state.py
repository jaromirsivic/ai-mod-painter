"""Per-layer view state (order, visible, red) and its carry-over between animations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ai_mod_painter.core.library import Layer


@dataclass(frozen=True)
class LayerState:
    key: str
    name: str
    visible: bool = True
    red: bool = False


class LayerMemory:
    """Remembers the layer state of the animations seen so far, by layer key.

    In memory only. ``apply`` turns the default layer order of a newly opened animation
    into the remembered set-up: layers known from earlier animations get their flags and
    their remembered relative order (sorted among the positions the known layers take in
    the default order); new layers keep their default position and default flags.
    ``remember`` stores the current state; layers absent from the current animation stay
    remembered for later ones.
    """

    def __init__(self) -> None:
        self._order: list[str] = []
        self._flags: dict[str, tuple[bool, bool]] = {}

    def apply(self, layers: Sequence[Layer]) -> list[LayerState]:
        """Layer states bottom first for ``layers`` (given in default order, bottom first)."""
        rank = {key: i for i, key in enumerate(self._order)}
        keys = [layer.key for layer in layers]
        known_slots = [i for i, key in enumerate(keys) if key in rank]
        known_sorted = sorted((keys[i] for i in known_slots), key=rank.__getitem__)
        for slot, key in zip(known_slots, known_sorted, strict=True):
            keys[slot] = key

        by_key = {layer.key: layer for layer in layers}
        states = []
        for key in keys:
            visible, red = self._flags.get(key, (True, False))
            states.append(LayerState(key=key, name=by_key[key].name, visible=visible, red=red))
        return states

    def remember(self, states: Sequence[LayerState]) -> None:
        current = [s.key for s in states]
        current_set = set(current)
        old = self._order
        old_set = set(old)

        # Present keys that were already known take the slots they had, in current order.
        order = list(old)
        slots = [i for i, key in enumerate(old) if key in current_set]
        for slot, key in zip(slots, [k for k in current if k in old_set], strict=True):
            order[slot] = key

        # New keys go right after the key below them in the current order.
        for i, key in enumerate(current):
            if key in old_set:
                continue
            below = current[i - 1] if i > 0 else None
            position = order.index(below) + 1 if below is not None else 0
            order.insert(position, key)

        self._order = order
        for s in states:
            self._flags[s.key] = (s.visible, s.red)

    def clear(self) -> None:
        self._order.clear()
        self._flags.clear()
