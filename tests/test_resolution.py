from __future__ import annotations

from ai_mod_painter.core.library import scan_animation
from ai_mod_painter.core.resolution import describe_sizes, image_sizes, is_uniform


def test_same_sizes_are_uniform(make_tree):
    root = make_tree({"a/f0/x.png": {"size": (8, 4)}, "a/f1/y.png": {"size": (8, 4)}})
    sizes = image_sizes(scan_animation(root / "a"))
    assert sizes == {(8, 4): 2}
    assert is_uniform(sizes)


def test_every_image_of_every_frame_counts(make_tree):
    root = make_tree(
        {
            "a/f0/x.png": {"size": (8, 4)},
            "a/f0/mask.png": {"size": (8, 4)},
            "a/f1/x.png": {"size": (8, 4)},
            "a/f1/mask.png": {"size": (16, 8)},
        }
    )
    sizes = image_sizes(scan_animation(root / "a"))
    assert sizes == {(8, 4): 3, (16, 8): 1}
    assert not is_uniform(sizes)
    assert describe_sizes(sizes) == "8 x 4 (3), 16 x 8 (1)"


def test_unreadable_images_are_left_out(make_tree):
    root = make_tree({"a/f0/x.png": {"size": (8, 4)}, "a/f1/broken.png": None})
    (root / "a" / "f1" / "broken.png").write_bytes(b"not an image")
    sizes = image_sizes(scan_animation(root / "a"))
    assert sizes == {(8, 4): 1}
    assert is_uniform(sizes)
    assert is_uniform({})
