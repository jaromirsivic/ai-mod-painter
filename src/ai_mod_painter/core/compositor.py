"""Compose one frame from its layer images (Qt ``QImage``, works without a window)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from ai_mod_painter.core.layer_state import LayerState
from ai_mod_painter.core.library import Frame

RED = QColor(255, 0, 0)
WORK_FORMAT = QImage.Format.Format_ARGB32_Premultiplied

ImageOf = Callable[[Path], QImage | None]
SizeOf = Callable[[Path], QSize]


def canvas_layer(frame: Frame, states: Sequence[LayerState]) -> LayerState | None:
    """The bottom-most layer present in the frame (visible or not): it gives the size."""
    for state in states:
        if state.key in frame.files:
            return state
    return None


def needed_paths(frame: Frame, states: Sequence[LayerState]) -> list[Path]:
    """Image files that must be decoded to draw the frame (visible layers, bottom first)."""
    return [frame.files[s.key] for s in states if s.visible and s.key in frame.files]


def red_mask(image: QImage) -> QImage:
    """Opaque pixels become red, alpha is kept (transparent stays transparent)."""
    out = image.convertToFormat(WORK_FORMAT)
    painter = QPainter(out)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(out.rect(), RED)
    painter.end()
    return out


def compose(
    frame: Frame,
    states: Sequence[LayerState],
    image_of: ImageOf,
    size_of: SizeOf,
) -> QImage | None:
    """Draw the visible layers bottom -> top onto a canvas of the bottom layer's size.

    ``states`` are bottom first. Images of another size are stretched to the canvas
    (aspect ratio ignored). An image that ``image_of`` cannot give (unreadable file) is
    left out. Returns ``None`` when the frame has none of the layers or the canvas
    layer's size is unknown.
    """
    base = canvas_layer(frame, states)
    if base is None:
        return None
    size = size_of(frame.files[base.key])
    if not size.isValid() or size.isEmpty():
        return None

    canvas = QImage(size, WORK_FORMAT)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for state in states:
        if not state.visible or state.key not in frame.files:
            continue
        image = image_of(frame.files[state.key])
        if image is None or image.isNull():
            continue
        if image.size() != size:
            image = image.scaled(
                size,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        if state.red:
            image = red_mask(image)
        painter.drawImage(0, 0, image)
    painter.end()
    return canvas


def straight_color(image: QImage, x: int, y: int) -> QColor:
    """The non-premultiplied colour of one pixel."""
    pixel = image.copy(x, y, 1, 1).convertToFormat(QImage.Format.Format_ARGB32)
    return pixel.pixelColor(0, 0)
