from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from ai_mod_painter.ui.image_view import MAX_ZOOM, MIN_ZOOM
from ai_mod_painter.ui.main_window import MainWindow
from tests.conftest import make_image

BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)


@pytest.fixture
def window(qtbot, settings):
    win = MainWindow(settings=settings)
    qtbot.addWidget(win)
    win.resize(1200, 800)
    win.show()
    qtbot.waitExposed(win)
    yield win
    win.close()


def frame_tree(make_tree, frames=3, name="anim", extra=None):
    """Frames with a blue base layer and a frame-specific green dot in a top layer."""
    spec: dict[str, object] = {}
    for i in range(frames):
        spec[f"{name}/frame{i}/base.png"] = {"size": (8, 4), "color": BLUE}
        spec[f"{name}/frame{i}/top.png"] = {
            "size": (8, 4),
            "color": (0, 0, 0, 0),
            "pixels": {(i, 0): GREEN},
        }
    spec.update(extra or {})
    return make_tree(spec)


def open_first(qtbot, window, root):
    assert window.open_root(root)
    with qtbot.waitSignal(window.animation_loaded, timeout=5000):
        window.animations.select_row(0)
    qtbot.waitUntil(lambda: window.shown_index == window.frame_index, timeout=5000)


def pixel(window, x, y):
    color = window.image.pixelColor(x, y)
    return color.red(), color.green(), color.blue(), color.alpha()


def test_panels_toggle_from_menu_and_bar(window):
    assert window.panel_visible(window.animations)
    window.show_animations_action.setChecked(False)
    assert not window.panel_visible(window.animations)
    assert not window.master.left_toggle.isChecked()
    window.master.left_toggle.setChecked(True)
    assert window.panel_visible(window.animations)

    window.master.right_toggle.setChecked(False)
    assert not window.panel_visible(window.layers)
    assert not window.show_layers_action.isChecked()
    window.show_layers_action.setChecked(True)
    assert window.panel_visible(window.layers)


def test_pagination_of_many_animations(qtbot, window, make_tree):
    root = make_tree({f"anim{i}/": None for i in range(250)})
    assert window.open_root(root)
    panel = window.animations
    assert panel.page_total() == 3
    assert len(panel.visible_animations()) == 100
    assert panel.visible_animations()[0].name == "anim0"
    assert panel.visible_animations()[1].name == "anim1"
    panel.set_page(2)
    assert [p.name for p in panel.visible_animations()][:2] == ["anim200", "anim201"]
    assert len(panel.visible_animations()) == 50
    panel.set_page(5)
    assert panel.current_page == 2


def test_open_root_error_is_shown(window, tmp_path):
    assert not window.open_root(tmp_path / "missing")
    assert "Cannot open" in window.message_label.text()


def test_open_animation_shows_first_frame_and_layers(qtbot, window, make_tree):
    root = frame_tree(make_tree, extra={"anim/frame0/scene.json": "{}", "anim/frame9/x.json": "{}"})
    open_first(qtbot, window, root)

    assert len(window.animation.frames) == 3  # frame9 has no images: skipped
    assert window.master.label.text() == "frame0  (1 / 3)"
    assert [s.key for s in window.layers.states()] == ["base.png", "top.png"]
    assert pixel(window, 0, 0) == GREEN
    assert pixel(window, 1, 0) == BLUE
    assert window.size_label.text().startswith("8 x 4")


def test_slider_changes_the_frame(qtbot, window, make_tree):
    open_first(qtbot, window, frame_tree(make_tree))
    window.master.slider.setValue(2)
    qtbot.waitUntil(lambda: window.shown_index == 2, timeout=5000)
    assert pixel(window, 2, 0) == GREEN
    assert pixel(window, 0, 0) == BLUE
    assert window.master.label.text() == "frame2  (3 / 3)"


def test_layer_changes_recompose(qtbot, window, make_tree):
    open_first(qtbot, window, frame_tree(make_tree))

    window.layers.set_red("top.png", True)
    qtbot.waitUntil(lambda: window.shown_index == 0 and pixel(window, 0, 0)[:3] == (255, 0, 0))

    window.layers.set_visible("top.png", False)
    qtbot.waitUntil(lambda: window.shown_index == 0 and pixel(window, 0, 0) == BLUE)

    window.layers.set_visible("top.png", True)
    window.layers.set_red("top.png", False)
    window.layers.move_to_row("base.png", 0)  # base on top now covers the green dot
    qtbot.waitUntil(lambda: [s.key for s in window.layers.states()] == ["top.png", "base.png"])
    qtbot.waitUntil(lambda: window.shown_index == 0 and pixel(window, 0, 0) == BLUE)


def test_layer_toggle_by_clicking_the_icons(qtbot, window, make_tree):
    open_first(qtbot, window, frame_tree(make_tree))
    view = window.layers.list_widget
    rect = view.visualItemRect(view.item(0))  # top row: top.png
    eye = QPoint(rect.left() + 4 + 9, rect.center().y())
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=eye)
    assert not window.layers.states()[1].visible
    qtbot.waitUntil(lambda: window.shown_index == 0 and pixel(window, 0, 0) == BLUE)


def test_layer_state_carries_over_to_next_animation(qtbot, window, make_tree):
    root = frame_tree(make_tree, name="a1")
    frame_tree(make_tree, name="a2")
    open_first(qtbot, window, root)
    window.layers.set_visible("top.png", False)

    with qtbot.waitSignal(window.animation_loaded, timeout=5000):
        window.animations.select_row(1)
    states = {s.key: s.visible for s in window.layers.states()}
    assert states == {"base.png": True, "top.png": False}


def test_animation_without_images(qtbot, window, make_tree):
    root = make_tree({"empty/frame0/scene.json": "{}"})
    assert window.open_root(root)
    with qtbot.waitSignal(window.animation_loaded, timeout=5000):
        window.animations.select_row(0)
    assert window.view.message() == "No images in this animation"
    assert not window.master.play_button.isEnabled()
    window.toggle_play()
    assert not window.is_playing()


def test_playback_loops_until_stop(qtbot, window, make_tree):
    open_first(qtbot, window, frame_tree(make_tree))
    window.play()
    assert window.is_playing()
    seen = []
    for _ in range(4):
        window._on_tick()
        qtbot.waitUntil(lambda: window.shown_index == window.frame_index, timeout=5000)
        seen.append(window.frame_index)
    assert seen == [1, 2, 0, 1]  # wraps from the last frame to the first
    window.toggle_play()
    assert not window.is_playing()
    assert window.master.play_button.text() == "▶"


def test_playback_holds_a_frame_that_is_not_decoded(qtbot, window, make_tree):
    open_first(qtbot, window, frame_tree(make_tree))
    window.play()
    window._shown_index = None  # pretend the current frame is still decoding
    window._on_tick()
    assert window.frame_index == 0


def test_playback_runs_on_the_timer_and_stops_on_animation_switch(qtbot, window, make_tree):
    root = frame_tree(make_tree, name="a1")
    frame_tree(make_tree, name="a2")
    open_first(qtbot, window, root)
    window.play()
    qtbot.waitUntil(lambda: window.frame_index == 2, timeout=5000)
    with qtbot.waitSignal(window.animation_loaded, timeout=5000):
        window.animations.select_row(1)
    assert not window.is_playing()


def test_reload_picks_up_new_frames(qtbot, window, make_tree, tmp_path):
    root = frame_tree(make_tree, frames=2)
    open_first(qtbot, window, root)
    window.master.slider.setValue(1)
    qtbot.waitUntil(lambda: window.shown_index == 1)
    make_image(root / "anim" / "frame2" / "base.png", size=(8, 4), color=BLUE)
    with qtbot.waitSignal(window.animation_loaded, timeout=5000):
        window.reload()
    assert len(window.animation.frames) == 3
    assert window.frame_index == 1  # stays on the same frame folder


def test_status_shows_pixel_under_cursor_and_zoom(qtbot, window, make_tree):
    open_first(qtbot, window, frame_tree(make_tree))
    view = window.view
    for zoom in (1.0, 4.0):
        view.set_zoom(zoom)
        view.centerOn(0, 0)
        target = view.mapFromScene(0.5, 0.5)
        move = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            target.toPointF(),
            view.viewport().mapToGlobal(target).toPointF(),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(view.viewport(), move)
        # At 1x the integer view position can land on a neighbouring pixel; at 4x it
        # is inside pixel 0,0 for sure. Either way the label names the pixel and its colour.
        point = view.image_point_at(target)
        assert point is not None
        if zoom >= 4:
            assert (point.x(), point.y()) == (0, 0)
        expected = "#00FF00FF" if (point.x(), point.y()) == (0, 0) else "#0000FFFF"
        assert window.pixel_label.text() == f"{point.x()},{point.y()}  {expected}"
        assert window.zoom_label.text() == f"{zoom * 100:.0f} %"
    QApplication.sendEvent(view.viewport(), QEvent(QEvent.Type.Leave))
    assert window.pixel_label.text() == ""


def test_zoom_is_clamped(window):
    view = window.view
    view.set_zoom(1000)
    assert view.zoom() == MAX_ZOOM
    assert window.zoom_label.text() == "6400 %"
    view.set_zoom(0.0001)
    assert view.zoom() == pytest.approx(MIN_ZOOM)
    assert window.zoom_label.text() == "1.6 %"
    view.set_zoom(1)
    view.zoom_by_steps(4)
    assert view.zoom() == pytest.approx(2.0)
