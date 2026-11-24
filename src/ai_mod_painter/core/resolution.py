"""Do all images of an animation have the same size?

Universal: every image of every frame counts, whatever its name. Only the image headers
are read (no decoding), so this is cheap enough to run with every scan.
"""

from __future__ import annotations

from PySide6.QtGui import QImageReader

from ai_mod_painter.core.library import Animation

Size = tuple[int, int]


def image_sizes(animation: Animation) -> dict[Size, int]:
    """(width, height) -> number of images of that size; unreadable images are left out."""
    sizes: dict[Size, int] = {}
    for frame in animation.frames:
        for path in frame.files.values():
            size = QImageReader(str(path)).size()
            if not size.isValid() or size.isEmpty():
                continue
            key = (size.width(), size.height())
            sizes[key] = sizes.get(key, 0) + 1
    return sizes


def is_uniform(sizes: dict[Size, int]) -> bool:
    return len(sizes) <= 1


def describe_sizes(sizes: dict[Size, int]) -> str:
    """``1672 x 941 (140), 1920 x 1080 (10)``: the most frequent size first."""
    ordered = sorted(sizes.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{w} x {h} ({count})" for (w, h), count in ordered)
