from __future__ import annotations

from ai_mod_painter.core.layer_presets import default_preset, keep_states
from ai_mod_painter.core.layer_state import LayerState
from ai_mod_painter.core.library import Layer, layer_key


def layers(*names: str) -> list[Layer]:
    """Layers in the library's default order (bottom first)."""
    return [Layer(key=layer_key(n), name=n, frame_count=1) for n in names]


def flags(states: list[LayerState]) -> list[tuple[str, bool, bool]]:
    return [(s.key, s.visible, s.red) for s in states]


def test_scene_at_the_bottom_render_above_aircraft_masked():
    states = default_preset(
        layers("aircraft_aircraft-09_sun.png", "render.png", "extra.png", "render_scene.png")
    )
    assert flags(states) == [
        ("render_scene.png", False, False),
        ("render.png", True, False),
        ("aircraft_aircraft-09_sun.png", False, True),
        ("extra.png", True, False),
    ]


def test_render_at_the_bottom_without_a_scene_and_names_keep_their_case():
    states = default_preset(layers("Render_AIRCRAFT.png", "Render.PNG"))
    assert flags(states) == [
        ("render.png", True, False),
        ("render_aircraft.png", False, True),
    ]
    assert [s.name for s in states] == ["Render.PNG", "Render_AIRCRAFT.png"]


def test_tree_without_the_names_keeps_the_generic_order():
    states = default_preset(layers("base.png", "top.png"))
    assert flags(states) == [("base.png", True, False), ("top.png", True, False)]


def test_keep_states_keeps_the_setup_drops_gone_layers_and_places_new_ones():
    current = [
        LayerState("b", "b", visible=False),
        LayerState("a", "a", red=True),
        LayerState("gone", "gone"),
    ]
    preset = [LayerState("a", "a"), LayerState("new", "new", visible=False), LayerState("b", "b")]
    assert flags(keep_states(current, preset)) == [
        ("b", False, False),
        ("a", True, True),
        ("new", False, False),  # above "a", the layer below it in the preset
    ]


def test_keep_states_puts_a_new_lowest_layer_at_the_bottom():
    preset = [LayerState("new", "new"), LayerState("a", "a")]
    assert [s.key for s in keep_states([LayerState("a", "a")], preset)] == ["new", "a"]
