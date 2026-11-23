from __future__ import annotations

from PySide6.QtCore import QSize

from ai_mod_painter.core.compositor import compose, needed_paths, red_mask, straight_color
from ai_mod_painter.core.image_cache import ImageCache
from ai_mod_painter.core.layer_state import LayerState
from ai_mod_painter.core.library import Frame
from tests.conftest import make_image

TRANSPARENT = (0, 0, 0, 0)


def rgba(image, x, y):
    color = straight_color(image, x, y)
    return color.red(), color.green(), color.blue(), color.alpha()


def setup(tmp_path, specs):
    """specs: {name: make_image kwargs}; returns frame, cache."""
    files = {}
    for name, kwargs in specs.items():
        files[name] = make_image(tmp_path / name, **kwargs)
    cache = ImageCache()
    for path in files.values():
        cache.load_now(path)
    return Frame(name="frame0", path=tmp_path, files=files), cache


def states(*specs) -> list[LayerState]:
    result = []
    for spec in specs:
        key, *flags = spec.split(":")
        result.append(LayerState(key, key, visible="hidden" not in flags, red="red" in flags))
    return result


def draw(frame, cache, layer_states):
    return compose(frame, layer_states, cache.get, cache.size_of)


def test_stacking_bottom_to_top_with_alpha(qapp, tmp_path):
    frame, cache = setup(
        tmp_path,
        {
            "bottom.png": {"color": (0, 0, 255, 255)},
            "top.png": {"color": TRANSPARENT, "pixels": {(1, 1): (0, 255, 0, 255)}},
        },
    )
    image = draw(frame, cache, states("bottom.png", "top.png"))
    assert rgba(image, 0, 0) == (0, 0, 255, 255)
    assert rgba(image, 1, 1) == (0, 255, 0, 255)

    # Reversed: the opaque blue layer covers the green pixel.
    image = draw(frame, cache, states("top.png", "bottom.png"))
    assert rgba(image, 1, 1) == (0, 0, 255, 255)


def test_opaque_jpg_covers_everything_below(qapp, tmp_path):
    frame, cache = setup(
        tmp_path,
        {"a.png": {"color": (0, 0, 255, 255)}, "b.jpg": {"color": (255, 255, 255, 255)}},
    )
    image = draw(frame, cache, states("a.png", "b.jpg"))
    r, g, b, a = rgba(image, 2, 2)
    assert a == 255 and min(r, g, b) > 240


def test_red_mask_keeps_alpha(qapp, tmp_path):
    frame, cache = setup(
        tmp_path,
        {
            "base.png": {"color": TRANSPARENT},
            "obj.png": {
                "color": TRANSPARENT,
                "pixels": {(0, 0): (10, 200, 30, 255), (1, 0): (10, 200, 30, 128)},
            },
        },
    )
    image = draw(frame, cache, states("base.png", "obj.png:red"))
    assert rgba(image, 0, 0) == (255, 0, 0, 255)
    r, g, b, a = rgba(image, 1, 0)
    assert (r, g, b) == (255, 0, 0) and abs(a - 128) <= 1
    assert rgba(image, 3, 3) == TRANSPARENT

    masked = red_mask(cache.get(frame.files["obj.png"]))
    assert rgba(masked, 2, 2) == TRANSPARENT


def test_layers_stretch_to_the_bottom_layer_size(qapp, tmp_path):
    frame, cache = setup(
        tmp_path,
        {"small.png": {"size": (2, 2), "color": (0, 0, 255, 255)}, "big.png": {"size": (8, 4)}},
    )
    image = draw(frame, cache, states("small.png", "big.png"))
    assert image.size() == QSize(2, 2)
    image = draw(frame, cache, states("big.png", "small.png"))
    assert image.size() == QSize(8, 4)
    assert rgba(image, 7, 3) == (0, 0, 255, 255)  # small image stretched over the canvas


def test_missing_bottom_layer_uses_lowest_present_one(qapp, tmp_path):
    frame, cache = setup(tmp_path, {"b.png": {"size": (6, 3)}})
    image = draw(frame, cache, states("a.png", "b.png"))
    assert image.size() == QSize(6, 3)


def test_hidden_bottom_layer_still_gives_size_and_all_hidden_is_empty(qapp, tmp_path):
    frame, cache = setup(tmp_path, {"a.png": {"size": (5, 3)}, "b.png": {"size": (2, 2)}})
    image = draw(frame, cache, states("a.png:hidden", "b.png:hidden"))
    assert image.size() == QSize(5, 3)
    assert rgba(image, 0, 0) == TRANSPARENT
    assert needed_paths(frame, states("a.png:hidden", "b.png")) == [frame.files["b.png"]]


def test_unreadable_image_is_left_out(qapp, tmp_path):
    frame, cache = setup(tmp_path, {"a.png": {"color": (0, 0, 255, 255)}})
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not an image")
    frame.files["broken.png"] = broken
    cache.load_now(broken)
    assert cache.is_ready(broken) and cache.get(broken) is None
    image = draw(frame, cache, states("a.png", "broken.png"))
    assert rgba(image, 0, 0) == (0, 0, 255, 255)
