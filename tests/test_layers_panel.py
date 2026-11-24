from __future__ import annotations

from ai_mod_painter.core.layer_state import LayerState
from ai_mod_painter.ui.layers_panel import CUSTOM_MODE, DEFAULT_MODE, LayersPanel


def test_toggle_visible_flips_the_eye_like_a_click(qtbot):
    panel = LayersPanel()
    qtbot.addWidget(panel)
    panel.set_layers([LayerState("a.png", "a.png"), LayerState("b.png", "b.png", visible=False)])
    panel.set_mode(DEFAULT_MODE)

    with qtbot.waitSignal(panel.changed, timeout=1000):
        assert panel.toggle_visible("b.png") is True
    assert {s.key: s.visible for s in panel.states()} == {"a.png": True, "b.png": True}
    assert panel.mode() == CUSTOM_MODE
    assert panel.toggle_visible("b.png") is True
    assert {s.key: s.visible for s in panel.states()}["b.png"] is False


def test_toggle_visible_of_an_unknown_layer_does_nothing(qtbot):
    panel = LayersPanel()
    qtbot.addWidget(panel)
    panel.set_layers([LayerState("a.png", "a.png")])
    panel.set_mode(DEFAULT_MODE)
    with qtbot.assertNotEmitted(panel.changed):
        assert panel.toggle_visible("missing.png") is False
    assert panel.mode() == DEFAULT_MODE
