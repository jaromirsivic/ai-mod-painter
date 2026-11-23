"""The main image area: wheel zoom 1/64x..64x anchored at the cursor, drag to pan."""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QWidget,
)

MIN_ZOOM = 1 / 64
MAX_ZOOM = 64.0
ZOOM_STEP = 2 ** (1 / 4)  # one wheel notch
BACKGROUND = QColor(48, 48, 48)


def clamp_zoom(zoom: float) -> float:
    return min(max(zoom, MIN_ZOOM), MAX_ZOOM)


def format_zoom(zoom: float) -> str:
    percent = zoom * 100
    return f"{percent:.1f} %" if percent < 10 else f"{percent:.0f} %"


class ImageView(QGraphicsView):
    zoom_changed = Signal(float)
    hover_changed = Signal(object)  # QPoint in image pixels, or None outside the image

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)
        self.setScene(self._scene)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(BACKGROUND)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        self._pan_from: QPoint | None = None
        self._hover: QPoint | None = None
        self._last_pos: QPoint | None = None

        self._message = QLabel(self.viewport())
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setStyleSheet("color: #c8c8c8; font-size: 14px;")
        self._message.hide()
        self._apply_smoothing()

    # --- content -----------------------------------------------------------------------

    def has_image(self) -> bool:
        return not self._item.pixmap().isNull()

    def set_image(self, image: QImage | None) -> None:
        """Show an image; the zoom and scroll position are kept."""
        if image is None or image.isNull():
            self._item.setPixmap(QPixmap())
            self._scene.setSceneRect(QRectF())
        else:
            self._item.setPixmap(QPixmap.fromImage(image))
            self._scene.setSceneRect(QRectF(image.rect()))
        self._update_hover()

    def set_message(self, text: str) -> None:
        self._message.setText(text)
        self._message.setVisible(bool(text))
        self._place_message()

    def message(self) -> str:
        return self._message.text() if self._message.isVisible() else ""

    # --- zoom --------------------------------------------------------------------------

    def zoom(self) -> float:
        return self.transform().m11()

    def set_zoom(self, zoom: float) -> None:
        zoom = clamp_zoom(zoom)
        current = self.zoom()
        if math.isclose(zoom, current, rel_tol=1e-9):
            return
        factor = zoom / current
        self.scale(factor, factor)
        self._after_zoom()

    def zoom_by_steps(self, steps: float) -> None:
        self.set_zoom(self.zoom() * ZOOM_STEP**steps)

    def fit(self) -> None:
        """Fit the whole image into the window (within the zoom range)."""
        rect = self._scene.sceneRect()
        if rect.isEmpty():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        zoom = self.zoom()
        if clamp_zoom(zoom) != zoom:
            self.resetTransform()
            self.scale(clamp_zoom(zoom), clamp_zoom(zoom))
            self.centerOn(rect.center())
        self._after_zoom()

    def actual_size(self) -> None:
        self.set_zoom(1.0)

    def _after_zoom(self) -> None:
        self._apply_smoothing()
        self._update_hover()
        self.zoom_changed.emit(self.zoom())

    def _apply_smoothing(self) -> None:
        # Zoomed in: sharp pixels to inspect them. Zoomed out: smooth downscaling.
        smooth = self.zoom() < 1.0
        self._item.setTransformationMode(
            Qt.TransformationMode.SmoothTransformation
            if smooth
            else Qt.TransformationMode.FastTransformation
        )
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)

    # --- events ------------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        self.zoom_by_steps(delta / 120)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._pan_from = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()
        if self._pan_from is not None:
            delta = pos - self._pan_from
            self._pan_from = pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        self._last_pos = pos
        self._update_hover()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._pan_from is not None and event.button() in (
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.MiddleButton,
        ):
            self._pan_from = None
            self.viewport().unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def viewportEvent(self, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Leave:  # off the image area (also onto a scrollbar)
            self._last_pos = None
            self._update_hover()
        return super().viewportEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_message()

    def _place_message(self) -> None:
        self._message.setGeometry(self.viewport().rect())

    # --- hover -------------------------------------------------------------------------

    def image_point_at(self, view_pos: QPoint) -> QPoint | None:
        """The image pixel under a viewport position, or ``None`` outside the image."""
        if not self.has_image():
            return None
        scene: QPointF = self.mapToScene(view_pos)
        x, y = math.floor(scene.x()), math.floor(scene.y())
        size = self._item.pixmap().size()
        if 0 <= x < size.width() and 0 <= y < size.height():
            return QPoint(x, y)
        return None

    def hover_point(self) -> QPoint | None:
        return self._hover

    def _update_hover(self) -> None:
        # Emitted also when the point did not move: the frame or the image under it may
        # have changed, so the colour shown for it must be read again.
        point = self.image_point_at(self._last_pos) if self._last_pos is not None else None
        self._hover = point
        self.hover_changed.emit(point)
