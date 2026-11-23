from __future__ import annotations

import pytest

from ai_mod_painter.core.library import (
    list_animations,
    natural_key,
    page,
    page_count,
    scan_animation,
)


def test_natural_key_orders_numbers_by_value():
    names = ["frame10", "frame2", "Frame1", "frame0", "f_10", "f_9", "a", "a1"]
    assert sorted(names, key=natural_key) == [
        "a",
        "a1",
        "f_9",
        "f_10",
        "frame0",
        "Frame1",
        "frame2",
        "frame10",
    ]


def test_list_animations_sorted_ascending_folders_only(make_tree):
    root = make_tree(
        {
            "2026-11-23-16-47-07/": None,
            "2026-11-23-15-49-16/": None,
            "anim10/": None,
            "anim2/": None,
            "notes.txt": "ignored",
        }
    )
    assert [p.name for p in list_animations(root)] == [
        "2026-11-23-15-49-16",
        "2026-11-23-16-47-07",
        "anim2",
        "anim10",
    ]


def test_list_animations_missing_root_raises(tmp_path):
    with pytest.raises(OSError):
        list_animations(tmp_path / "missing")


def test_pagination():
    items = list(range(250))
    assert page_count(len(items)) == 3
    assert page_count(0) == 1
    assert page(items, 0) == list(range(100))
    assert page(items, 2) == list(range(200, 250))
    assert page(items, 9) == list(range(200, 250))  # clamped
    assert page([], 0) == []


def test_scan_example_shape(make_tree):
    """The shape of the example render output: images only in frames 0-9, JSON everywhere."""
    spec: dict[str, object] = {"anim/animation.json": "{}"}
    for i in range(30):
        spec[f"anim/frame{i}/scene.json"] = "{}"
        if i < 10:
            for name in (
                "render.png",
                "render_aircraft.png",
                "aircraft_aircraft-01_sun.png",
                "aircraft_aircraft-04_sun.png",
            ):
                spec[f"anim/frame{i}/{name}"] = None
    spec["anim/frame0/render_scene.png"] = None
    root = make_tree(spec)

    animation = scan_animation(root / "anim")

    assert [f.name for f in animation.frames] == [f"frame{i}" for i in range(10)]
    assert [layer.name for layer in animation.layers] == [
        "aircraft_aircraft-01_sun.png",
        "aircraft_aircraft-04_sun.png",
        "render.png",
        "render_aircraft.png",
        "render_scene.png",  # 1 frame only: on top
    ]
    assert [layer.frame_count for layer in animation.layers] == [10, 10, 10, 10, 1]
    assert set(animation.frames[0].files) == {layer.key for layer in animation.layers}
    assert "render_scene.png" not in animation.frames[1].files


def test_scan_universal_names_and_extensions(make_tree):
    root = make_tree(
        {
            "shot/s_10/b.PNG": None,
            "shot/s_2/a.jpg": None,
            "shot/s_2/b.png": None,
            "shot/s_2/c.JPEG": None,
            "shot/s_2/readme.md": "x",
            "shot/s_2/deeper/x.png": None,  # deeper folders are not searched
        }
    )
    animation = scan_animation(root / "shot")
    assert [f.name for f in animation.frames] == ["s_2", "s_10"]
    assert [layer.name for layer in animation.layers] == ["b.png", "a.jpg", "c.JPEG"]
    # Layer keys ignore letter case: b.PNG in s_10 is the same layer as b.png.
    assert set(animation.frames[1].files) == {"b.png"}


def test_scan_empty_animations(make_tree):
    root = make_tree({"one/frame0/": None, "none/": None, "json/frame0/scene.json": "{}"})
    for name in ("one", "none", "json"):
        animation = scan_animation(root / name)
        assert animation.frames == []
        assert animation.layers == []


def test_scan_missing_animation_raises(tmp_path):
    with pytest.raises(OSError):
        scan_animation(tmp_path / "missing")
