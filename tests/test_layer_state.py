from __future__ import annotations

from dataclasses import replace

from ai_mod_painter.core.layer_state import LayerMemory, LayerState
from ai_mod_painter.core.library import Layer


def layers(*names: str) -> list[Layer]:
    return [Layer(key=n, name=n, frame_count=1) for n in names]


def keys(states: list[LayerState]) -> list[str]:
    return [s.key for s in states]


def test_defaults_without_memory():
    states = LayerMemory().apply(layers("a", "b", "c"))
    assert keys(states) == ["a", "b", "c"]
    assert all(s.visible and not s.red for s in states)


def test_known_layers_keep_flags_and_relative_order_new_ones_keep_defaults():
    memory = LayerMemory()
    first = memory.apply(layers("a", "b", "c"))
    # The user moves "a" to the top, hides "b" and makes "c" red.
    first = [replace(first[1], visible=False), replace(first[2], red=True), first[0]]
    memory.remember(first)  # bottom first: b, c, a

    second = memory.apply(layers("a", "x", "c", "y"))

    # Known a and c take the slots 0 and 2 in remembered order (c below a).
    assert keys(second) == ["c", "x", "a", "y"]
    flags = {s.key: (s.visible, s.red) for s in second}
    assert flags == {"c": (True, True), "x": (True, False), "a": (True, False), "y": (True, False)}


def test_absent_layer_is_remembered_for_later_animations():
    memory = LayerMemory()
    states = memory.apply(layers("a", "b"))
    memory.remember([replace(states[0], visible=False), states[1]])

    memory.remember(memory.apply(layers("c")))  # "a" and "b" are absent here

    third = memory.apply(layers("b", "a"))
    assert keys(third) == ["a", "b"]
    assert {s.key: s.visible for s in third} == {"a": False, "b": True}


def test_new_layer_is_ranked_after_the_layer_below_it():
    memory = LayerMemory()
    memory.remember(memory.apply(layers("a", "b")))
    memory.remember(memory.apply(layers("a", "n", "b")))  # n between a and b
    assert keys(memory.apply(layers("b", "n", "a"))) == ["a", "n", "b"]
