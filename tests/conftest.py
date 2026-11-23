from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402


def make_image(
    path: Path,
    size: tuple[int, int] = (4, 4),
    color: QColor | tuple = (0, 0, 255, 255),
    pixels: dict[tuple[int, int], tuple] | None = None,
) -> Path:
    """Write a small image; PNG keeps alpha, JPG does not."""
    image = QImage(size[0], size[1], QImage.Format.Format_ARGB32)
    image.fill(QColor(*color) if isinstance(color, tuple) else color)
    for (x, y), rgba in (pixels or {}).items():
        image.setPixelColor(x, y, QColor(*rgba))
    path.parent.mkdir(parents=True, exist_ok=True)
    assert image.save(str(path)), path
    return path


@pytest.fixture
def make_tree(tmp_path):
    """Create files from a {relative path: content} dict; images get a default picture."""

    def create(spec: dict[str, object], root: Path | None = None) -> Path:
        base = root or tmp_path / "root"
        base.mkdir(parents=True, exist_ok=True)
        for relative, content in spec.items():
            path = base / relative
            if relative.endswith("/"):
                path.mkdir(parents=True, exist_ok=True)
            elif path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                make_image(path, **(content or {}))
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(content or ""), encoding="utf-8")
        return base

    return create


@pytest.fixture
def settings(tmp_path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
