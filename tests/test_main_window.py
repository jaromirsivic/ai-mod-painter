from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLineEdit

from ai_mod_painter.core.prompt_queue import queue_file_name
from ai_mod_painter.core.review import CONFIG_NAME, read_approved
from ai_mod_painter.ui.animation_panel import thumb_rect, trash_rect
from ai_mod_painter.ui.image_view import MAX_ZOOM, MIN_ZOOM
from ai_mod_painter.ui.layers_panel import CUSTOM_MODE, DEFAULT_MODE
from ai_mod_painter.ui.main_window import MainWindow
from tests.conftest import make_image

BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)


@pytest.fixture
def window(qtbot, settings, tmp_path):
    win = MainWindow(
        settings=settings,
        prompts_dir=tmp_path / "prompts",
        queue_dir=tmp_path / "queue",
    )
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


# --- frame position and playback across animations --------------------------------------


def switch_to(qtbot, window, row):
    with qtbot.waitSignal(window.animation_loaded, timeout=5000):
        window.animations.select_row(row)
    qtbot.waitUntil(lambda: window.shown_index == window.frame_index, timeout=5000)


def test_frame_position_is_kept_when_the_next_animation_has_enough_frames(qtbot, window, make_tree):
    root = frame_tree(make_tree, frames=3, name="a1")
    frame_tree(make_tree, frames=5, name="a2")
    frame_tree(make_tree, frames=2, name="a3")
    open_first(qtbot, window, root)
    window.master.slider.setValue(2)
    qtbot.waitUntil(lambda: window.shown_index == 2, timeout=5000)

    switch_to(qtbot, window, 1)  # 5 frames: stays on the third frame
    assert window.frame_index == 2
    assert window.master.label.text() == "frame2  (3 / 5)"

    switch_to(qtbot, window, 2)  # 2 frames: back to the first frame
    assert window.frame_index == 0


def test_playback_keeps_running_on_animation_switch(qtbot, window, make_tree):
    root = frame_tree(make_tree, name="a1")
    frame_tree(make_tree, name="a2")
    open_first(qtbot, window, root)
    window.play()
    switch_to(qtbot, window, 1)
    assert window.is_playing()
    assert window.animation.name == "a2"


# --- layer modes ------------------------------------------------------------------------


def preset_tree(make_tree, names=("a1", "a2")):
    spec: dict[str, object] = {}
    for name in names:
        for file_name in ("render.png", "render_scene.png", "Render_Aircraft.png", "extra.png"):
            spec[f"{name}/frame0/{file_name}"] = {"size": (8, 4)}
    return make_tree(spec)


def test_default_preset_on_open_and_custom_after_a_change(qtbot, window, make_tree):
    open_first(qtbot, window, preset_tree(make_tree))
    states = window.layers.states()
    assert [s.key for s in states][:2] == ["render_scene.png", "render.png"]
    assert {s.key: (s.visible, s.red) for s in states} == {
        "render_scene.png": (False, False),
        "render.png": (True, False),
        "render_aircraft.png": (False, True),
        "extra.png": (True, False),
    }
    assert window.layers.mode() == DEFAULT_MODE

    window.layers.set_visible("extra.png", False)
    assert window.layers.mode() == CUSTOM_MODE

    switch_to(qtbot, window, 1)  # another animation: Default again
    assert window.layers.mode() == DEFAULT_MODE
    assert {s.key: s.visible for s in window.layers.states()}["extra.png"] is True


def test_clicking_an_eye_switches_to_custom(qtbot, window, make_tree):
    open_first(qtbot, window, preset_tree(make_tree))
    view = window.layers.list_widget
    rect = view.visualItemRect(view.item(0))
    eye = QPoint(rect.left() + 13, rect.center().y())
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=eye)
    assert window.layers.mode() == CUSTOM_MODE


def test_reorder_switches_to_custom_and_default_applies_the_preset_again(qtbot, window, make_tree):
    open_first(qtbot, window, preset_tree(make_tree))
    window.layers.move_to_row("render_scene.png", 0)
    qtbot.waitUntil(lambda: window.layers.mode() == CUSTOM_MODE, timeout=5000)
    assert window.layers.states()[-1].key == "render_scene.png"

    window.layers.mode_combo.activated.emit(0)  # the user picks Default
    assert window.layers.mode() == DEFAULT_MODE
    assert window.layers.states()[0].key == "render_scene.png"


def test_reload_keeps_the_custom_layer_setup(qtbot, window, make_tree):
    open_first(qtbot, window, preset_tree(make_tree))
    window.layers.set_visible("extra.png", False)
    with qtbot.waitSignal(window.animation_loaded, timeout=5000):
        window.reload()
    assert {s.key: s.visible for s in window.layers.states()}["extra.png"] is False
    assert window.layers.mode() == CUSTOM_MODE


# --- prompt queue -----------------------------------------------------------------------


def write_prompt(tmp_path, name="convert_summer", text="in {SOURCE_IMAGE} out {DESTINATION_IMAGE}"):
    folder = tmp_path / "prompts"
    folder.mkdir(exist_ok=True)
    (folder / f"{name}.md").write_text(text, encoding="utf-8")


def test_add_queues_the_filled_prompt_for_render_png(qtbot, window, make_tree, tmp_path):
    write_prompt(tmp_path)
    write_prompt(tmp_path, name="convert_winter")
    window.load_prompts()
    combo = window.master.prompt_combo
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "convert_summer",
        "convert_winter",
    ]
    root = make_tree(
        {"a1/frame0/render.png": {"size": (8, 4)}, "a1/frame1/other.png": {"size": (8, 4)}}
    )
    assert not window.master.add_button.isEnabled()  # no animation yet
    open_first(qtbot, window, root)
    assert window.master.add_button.isEnabled()

    window.master.add_button.click()
    window.master.add_button.click()  # same frame and prompt: the same queue file
    queued = list((tmp_path / "queue").iterdir())
    source = root / "a1" / "frame0" / "render.png"
    template = tmp_path / "prompts" / "convert_summer.md"
    assert [p.name for p in queued] == [queue_file_name(source, template)]
    destination = source.with_name("render-photo.png")
    assert queued[0].read_text(encoding="utf-8") == f"in {source} out {destination}"
    assert "Queued convert_summer for a1/frame0" in window.message_label.text()

    config = json.loads((root / "a1" / CONFIG_NAME).read_text(encoding="utf-8"))
    assert [(r["prompt"], r["frame"], r["queue_file"]) for r in config["prompts"]] == [
        ("convert_summer.md", "frame0", queued[0].name),
        ("convert_summer.md", "frame0", queued[0].name),
    ]
    assert all(r["queued_at"] for r in config["prompts"])

    window.master.slider.setValue(1)  # frame1 has no render.png
    assert not window.master.add_button.isEnabled()


def test_add_is_disabled_without_prompts(qtbot, window, make_tree):
    window.load_prompts()
    open_first(qtbot, window, make_tree({"a1/frame0/render.png": {"size": (8, 4)}}))
    assert window.master.prompt_combo.count() == 0
    assert not window.master.add_button.isEnabled()


# --- review: approve, mark, delete, reload ----------------------------------------------


def click_icon(qtbot, panel, row, rect_of):
    view = panel.list_widget
    rect = rect_of(view.visualItemRect(view.item(row)))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


def test_approve_writes_the_config_and_is_read_back(qtbot, window, make_tree):
    root = make_tree({"a1/": None, "a2/": None})
    assert window.open_root(root)
    panel = window.animations

    click_icon(qtbot, panel, 0, thumb_rect)
    assert read_approved(root / "a1")
    assert panel.is_approved(root / "a1")
    assert not panel.is_approved(root / "a2")
    assert panel.selected_animation() is None  # an icon click does not open the animation

    assert window.open_root(root)  # read back from the file
    assert panel.is_approved(root / "a1")

    click_icon(qtbot, panel, 0, thumb_rect)
    assert not panel.is_approved(root / "a1")
    config = json.loads((root / "a1" / CONFIG_NAME).read_text(encoding="utf-8"))
    assert config["approved"] is False
    assert config["approved_changed_at"]


def test_trash_marks_and_approve_clears_the_mark(qtbot, window, make_tree):
    root = make_tree({"a1/": None, "a2/": None})
    assert window.open_root(root)
    panel = window.animations
    assert not panel.delete_button.isEnabled()

    click_icon(qtbot, panel, 1, trash_rect)
    assert panel.is_marked(root / "a2")
    assert panel.delete_button.isEnabled()
    assert panel.delete_button.text() == "Delete Selected (1)"
    assert not (root / "a2" / CONFIG_NAME).exists()  # marking writes nothing

    click_icon(qtbot, panel, 1, thumb_rect)
    assert not panel.is_marked(root / "a2")
    assert panel.is_approved(root / "a2")
    assert not panel.delete_button.isEnabled()


def test_delete_selected_asks_and_deletes_only_the_marked_folders(
    qtbot, window, make_tree, monkeypatch
):
    root = frame_tree(make_tree, name="a1")
    frame_tree(make_tree, name="a2")
    make_tree({"a3/frame0/scene.json": "{}"})
    open_first(qtbot, window, root)  # a1 is open
    panel = window.animations
    click_icon(qtbot, panel, 0, trash_rect)
    click_icon(qtbot, panel, 2, trash_rect)

    asked = []
    monkeypatch.setattr(window, "_confirm_delete", lambda count: asked.append(count) or False)
    panel.delete_button.click()
    assert asked == [2]
    assert (root / "a1").exists() and (root / "a3").exists()

    monkeypatch.setattr(window, "_confirm_delete", lambda count: True)
    panel.delete_button.click()
    assert not (root / "a1").exists()
    assert not (root / "a3").exists()
    assert (root / "a2").exists()
    assert window.animation is None  # the open animation was closed first
    assert [p.name for p in panel.animations] == ["a2"]
    assert not panel.delete_button.isEnabled()
    assert window.message_label.text() == "Deleted 2 animation folders"


def test_reload_button_goes_to_page_one_and_clears_marks_f5_keeps_both(qtbot, window, make_tree):
    root = make_tree({f"anim{i}/": None for i in range(150)})
    assert window.open_root(root)
    panel = window.animations
    panel.set_page(1)
    panel.toggle_marked(root / "anim120")
    make_tree({"anim150/": None})

    window.reload()  # F5
    assert panel.current_page == 1
    assert panel.is_marked(root / "anim120")
    assert len(panel.animations) == 151

    panel.reload_button.click()
    assert panel.current_page == 0
    assert not panel.marked_animations()


def test_trash_is_the_last_icon_of_the_row(window, make_tree):
    assert window.open_root(make_tree({"a1/": None}))
    view = window.animations.list_widget
    row = view.visualItemRect(view.item(0))
    assert trash_rect(row).left() > thumb_rect(row).left()
    assert trash_rect(row).right() <= row.right()


def row_state(panel, path):
    return panel.is_approved(path), panel.is_marked(path)


def test_the_last_of_approve_and_mark_wins(qtbot, window, make_tree):
    root = make_tree({"a1/": None})
    a1 = root / "a1"
    assert window.open_root(root)
    panel = window.animations

    click_icon(qtbot, panel, 0, thumb_rect)
    assert row_state(panel, a1) == (True, False)
    click_icon(qtbot, panel, 0, trash_rect)  # marking takes the approval back
    assert row_state(panel, a1) == (False, True)
    assert not read_approved(a1)
    click_icon(qtbot, panel, 0, thumb_rect)  # approving removes the mark
    assert row_state(panel, a1) == (True, False)
    click_icon(qtbot, panel, 0, thumb_rect)
    assert row_state(panel, a1) == (False, False)
    click_icon(qtbot, panel, 0, trash_rect)
    click_icon(qtbot, panel, 0, trash_rect)
    assert row_state(panel, a1) == (False, False)


# --- window-wide keys -------------------------------------------------------------------


def press(qtbot, widget, key, modifier=Qt.KeyboardModifier.NoModifier):
    widget.setFocus()
    qtbot.keyClick(widget, key, modifier)


def test_up_and_down_move_through_the_list_across_pages_and_stop_at_the_ends(
    qtbot, window, make_tree
):
    root = make_tree({f"anim{i}/": None for i in range(101)})
    assert window.open_root(root)
    panel = window.animations
    target = window.layers.list_widget  # keys work wherever the focus is

    press(qtbot, target, Qt.Key.Key_Up)  # nothing selected: ↑ takes the last row
    assert panel.selected_animation().name == "anim99"
    press(qtbot, target, Qt.Key.Key_Down)  # last row of page 1 -> first row of page 2
    assert panel.current_page == 1
    assert panel.selected_animation().name == "anim100"
    press(qtbot, target, Qt.Key.Key_Down)  # the very last animation: stays
    assert panel.selected_animation().name == "anim100"
    press(qtbot, target, Qt.Key.Key_Up)  # back to the last row of page 1
    assert panel.current_page == 0
    assert panel.selected_animation().name == "anim99"

    panel.select_row(0)
    press(qtbot, panel.list_widget, Qt.Key.Key_Up)  # the very first animation: stays
    assert panel.current_page == 0
    assert panel.selected_animation().name == "anim0"


def test_down_opens_the_next_animation(qtbot, window, make_tree):
    root = frame_tree(make_tree, name="a1")
    frame_tree(make_tree, name="a2")
    open_first(qtbot, window, root)
    with qtbot.waitSignal(window.animation_loaded, timeout=5000):
        press(qtbot, window.master.prompt_combo, Qt.Key.Key_Down)
    assert window.animation.name == "a2"


def test_left_and_right_step_through_the_frames_and_wrap(qtbot, window, make_tree):
    open_first(qtbot, window, frame_tree(make_tree, frames=3))
    target = window.animations.list_widget
    press(qtbot, target, Qt.Key.Key_Left)
    assert window.frame_index == 2
    press(qtbot, target, Qt.Key.Key_Right)
    assert window.frame_index == 0
    press(qtbot, target, Qt.Key.Key_Right)
    assert window.frame_index == 1


def test_a_and_d_act_on_the_selected_row(qtbot, window, make_tree):
    root = make_tree({"a1/": None, "a2/": None})
    assert window.open_root(root)
    panel = window.animations
    panel.select_row(1)
    a2 = root / "a2"
    target = panel.list_widget

    press(qtbot, target, Qt.Key.Key_A)
    assert row_state(panel, a2) == (True, False)
    assert read_approved(a2)
    press(qtbot, target, Qt.Key.Key_D)
    assert row_state(panel, a2) == (False, True)
    press(qtbot, target, Qt.Key.Key_A)
    assert row_state(panel, a2) == (True, False)
    press(qtbot, target, Qt.Key.Key_A)
    assert row_state(panel, a2) == (False, False)
    assert row_state(panel, root / "a1") == (False, False)


def test_ctrl_space_adds_the_prompt(qtbot, window, make_tree, tmp_path):
    write_prompt(tmp_path)
    window.load_prompts()
    open_first(qtbot, window, make_tree({"a1/frame0/render.png": {"size": (8, 4)}}))
    press(qtbot, window.layers.list_widget, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    assert len(list((tmp_path / "queue").iterdir())) == 1
    assert window.is_playing() is False  # Ctrl+Space is not Play


def test_text_field_keeps_arrows_and_letters(qtbot, window, make_tree):
    root = make_tree({"a1/": None, "a2/": None})
    assert window.open_root(root)
    panel = window.animations
    panel.select_row(0)
    field = panel.findChild(QLineEdit)
    field.setText("ab")
    field.setCursorPosition(2)
    press(qtbot, field, Qt.Key.Key_Left)
    press(qtbot, field, Qt.Key.Key_A)
    press(qtbot, field, Qt.Key.Key_Down)
    assert field.text() == "aab"
    assert panel.selected_animation().name == "a1"
    assert not panel.is_approved(root / "a1")
