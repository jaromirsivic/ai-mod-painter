"""The Default layer preset.

This module (with ``prompt_queue.py``) is the only place where layer names matter; see
CLAUDE.md. Trees without these names get the generic default order with every layer
visible.

Default, bottom first:

1. ``render_scene.png``: eye off, R off;
2. ``render.png``: eye on, R off (at the bottom when there is no scene layer);
3. ``render-photo.png``: eye on, R off, right above ``render.png``;
4. every other layer in the library's default order; a layer whose name contains
   ``aircraft`` gets R on and eye off, the others eye on and R off.

Ctrl+Space shows or hides ``render_aircraft.png`` (:data:`AIRCRAFT_LAYER`).

Names are compared without regard to letter case (layer keys are case-folded).
"""

from __future__ import annotations

from collections.abc import Sequence

from ai_mod_painter.core.layer_state import LayerState
from ai_mod_painter.core.library import Layer, layer_key

SCENE_LAYER = layer_key("render_scene.png")
RENDER_LAYER = layer_key("render.png")
PHOTO_LAYER = layer_key("render-photo.png")
"""What the prompt queue makes of ``render.png`` (see ``prompt_queue.py``)."""
AIRCRAFT_LAYER = layer_key("render_aircraft.png")
MASK_WORD = "aircraft"


def default_preset(layers: Sequence[Layer]) -> list[LayerState]:
    """Layer states bottom first for ``layers`` (given in the library's default order)."""
    by_key = {layer.key: layer for layer in layers}
    states: list[LayerState] = []
    if SCENE_LAYER in by_key:
        states.append(LayerState(SCENE_LAYER, by_key[SCENE_LAYER].name, visible=False))
    if RENDER_LAYER in by_key:
        states.append(LayerState(RENDER_LAYER, by_key[RENDER_LAYER].name))
    if PHOTO_LAYER in by_key:
        states.append(LayerState(PHOTO_LAYER, by_key[PHOTO_LAYER].name))
    for layer in layers:
        if layer.key in (SCENE_LAYER, RENDER_LAYER, PHOTO_LAYER):
            continue
        masked = MASK_WORD in layer.key
        states.append(LayerState(layer.key, layer.name, visible=not masked, red=masked))
    return states


def keep_states(current: Sequence[LayerState], preset: Sequence[LayerState]) -> list[LayerState]:
    """The current set-up for a rescanned animation (both lists bottom first).

    Layers that are still there keep their order and flags; layers gone from the rescan
    are dropped; new layers get the flags of ``preset`` and go right above the nearest
    layer that is below them in ``preset`` (or to the bottom).
    """
    preset_keys = {s.key for s in preset}
    result = [s for s in current if s.key in preset_keys]
    known = {s.key for s in result}
    for i, state in enumerate(preset):
        if state.key in known:
            continue
        position = 0
        for below in reversed(preset[:i]):
            if below.key in known:
                position = next(j for j, s in enumerate(result) if s.key == below.key) + 1
                break
        result.insert(position, state)
        known.add(state.key)
    return result
