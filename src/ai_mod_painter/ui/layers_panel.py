"""Right panel: the layers of the open animation, top row drawn on top.

Each row has an eye toggle (show / hide), a red toggle (red mask) and the file name.
Rows are reordered by drag and drop.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from PySide6.QtCore import QEvent, QModelIndex, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from ai_mod_painter.core.layer_state import LayerState

KEY_ROLE = Qt.ItemDataRole.UserRole + 1
VISIBLE_ROLE = Qt.ItemDataRole.UserRole + 2
RED_ROLE = Qt.ItemDataRole.UserRole + 3
PRESENT_ROLE = Qt.ItemDataRole.UserRole + 4

ROW_HEIGHT = 26
ICON = 18
EYE_X = 4
RED_X = EYE_X + ICON + 6
TEXT_X = RED_X + ICON + 8


def eye_rect(row: QRect) -> QRect:
    return QRect(row.left() + EYE_X, row.center().y() - ICON // 2, ICON, ICON)


def red_rect(row: QRect) -> QRect:
    return QRect(row.left() + RED_X, row.center().y() - ICON // 2, ICON, ICON)


class _LayerDelegate(QStyledItemDelegate):
    toggled = Signal(QModelIndex, int)  # index, role

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        size = super().sizeHint(option, index)
        return QSize(size.width() + TEXT_X, max(size.height(), ROW_HEIGHT))

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style is not None:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        visible = bool(index.data(VISIBLE_ROLE))
        red = bool(index.data(RED_ROLE))
        present = bool(index.data(PRESENT_ROLE))
        row = option.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_eye(painter, eye_rect(row), visible, opt)
        self._paint_red(painter, red_rect(row), red, opt)

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        palette = opt.palette
        color = palette.highlightedText().color() if selected else palette.text().color()
        if not present or not visible:
            color.setAlphaF(0.45)
        painter.setPen(color)
        text_rect = row.adjusted(TEXT_X, 0, -4, 0)
        elided = opt.fontMetrics.elidedText(text, Qt.TextElideMode.ElideMiddle, text_rect.width())
        align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        painter.drawText(text_rect, align, elided)
        painter.restore()

    @staticmethod
    def _paint_eye(painter: QPainter, rect: QRect, visible: bool, opt) -> None:
        color = opt.palette.text().color()
        if not visible:
            color.setAlphaF(0.35)
        pen = QPen(color, 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        r = rect.adjusted(1, 4, -1, -4)
        path = QPainterPath()
        path.moveTo(r.left(), r.center().y())
        path.quadTo(r.center().x(), r.top() - 3, r.right(), r.center().y())
        path.quadTo(r.center().x(), r.bottom() + 3, r.left(), r.center().y())
        painter.drawPath(path)
        if visible:
            painter.setBrush(color)
            painter.drawEllipse(rect.center(), 3, 3)
        else:
            painter.drawLine(rect.topLeft() + QPoint(2, 2), rect.bottomRight() - QPoint(2, 2))

    @staticmethod
    def _paint_red(painter: QPainter, rect: QRect, red: bool, opt) -> None:
        r = rect.adjusted(1, 1, -1, -1)
        font = QFont(opt.font)
        font.setBold(True)
        font.setPixelSize(11)
        painter.setFont(font)
        if red:
            painter.setPen(QPen(QColor(170, 0, 0), 1))
            painter.setBrush(QColor(255, 0, 0))
            painter.drawRoundedRect(r, 3, 3)
            painter.setPen(QColor(255, 255, 255))
        else:
            color = opt.palette.text().color()
            color.setAlphaF(0.4)
            painter.setPen(QPen(color, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(r, 3, 3)
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "R")

    def editorEvent(self, event: QEvent, model, option, index: QModelIndex) -> bool:  # noqa: N802
        if event.type() not in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
        ):
            return super().editorEvent(event, model, option, index)
        assert isinstance(event, QMouseEvent)
        if event.button() != Qt.MouseButton.LeftButton:
            return super().editorEvent(event, model, option, index)
        pos = event.position().toPoint()
        targets = ((eye_rect(option.rect), VISIBLE_ROLE), (red_rect(option.rect), RED_ROLE))
        for rect, role in targets:
            if rect.adjusted(-2, -2, 2, 2).contains(pos):
                if event.type() == QEvent.Type.MouseButtonRelease:
                    self.toggled.emit(index, role)
                return True  # also swallow press / double click: no drag, no selection
        return super().editorEvent(event, model, option, index)


class _LayerList(QListWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)
        self.setMouseTracking(True)


class LayersPanel(QWidget):
    """``states()`` / ``set_layers()`` use bottom-first order; the list shows top first."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = QLabel("Layers")
        self._title.setStyleSheet("font-weight: bold; padding: 4px 2px;")
        self._list = _LayerList(self)
        self._delegate = _LayerDelegate(self._list)
        self._list.setItemDelegate(self._delegate)
        self._delegate.toggled.connect(self._on_toggled)
        self._hint = QLabel("Drag to reorder. The top row is drawn on top.")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: gray; font-size: 11px; padding: 2px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(self._title)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._hint)

        self._loading = False
        self._emit_timer = QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.setInterval(0)
        self._emit_timer.timeout.connect(self._emit_if_order_changed)
        self._last_order: list[str] = []
        model = self._list.model()
        model.rowsMoved.connect(self._schedule_emit)
        model.rowsInserted.connect(self._schedule_emit)
        model.rowsRemoved.connect(self._schedule_emit)

    @property
    def list_widget(self) -> QListWidget:
        return self._list

    # --- content -----------------------------------------------------------------------

    def set_layers(
        self,
        states: Sequence[LayerState],
        counts: dict[str, int] | None = None,
        total_frames: int = 0,
    ) -> None:
        self._loading = True
        try:
            self._list.clear()
            for state in reversed(states):  # top of the list = top of the stack
                item = QListWidgetItem(state.name)
                item.setData(KEY_ROLE, state.key)
                item.setData(VISIBLE_ROLE, state.visible)
                item.setData(RED_ROLE, state.red)
                item.setData(PRESENT_ROLE, True)
                if counts is not None:
                    count = counts.get(state.key, 0)
                    item.setToolTip(f"{state.name} – {count} of {total_frames} frames")
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsDragEnabled
                )
                self._list.addItem(item)
        finally:
            self._loading = False
        self._last_order = [s.key for s in self.states()]

    def states(self) -> list[LayerState]:
        """Bottom first."""
        result = []
        for row in range(self._list.count() - 1, -1, -1):
            item = self._list.item(row)
            result.append(
                LayerState(
                    key=item.data(KEY_ROLE),
                    name=item.text(),
                    visible=bool(item.data(VISIBLE_ROLE)),
                    red=bool(item.data(RED_ROLE)),
                )
            )
        return result

    def set_present(self, keys: Iterable[str]) -> None:
        """Dim the layers that are not in the current frame."""
        present = set(keys)
        for row in range(self._list.count()):
            item = self._list.item(row)
            item.setData(PRESENT_ROLE, item.data(KEY_ROLE) in present)

    def set_visible(self, key: str, visible: bool) -> None:
        self._set_role(key, VISIBLE_ROLE, visible)

    def set_red(self, key: str, red: bool) -> None:
        self._set_role(key, RED_ROLE, red)

    def move_to_row(self, key: str, row: int) -> None:
        """Move a layer to a list row (0 = top of the stack)."""
        current = self._row_of(key)
        if current is None:
            return
        item = self._list.takeItem(current)
        self._list.insertItem(min(max(row, 0), self._list.count()), item)
        self._list.setCurrentItem(item)

    # --- internals ---------------------------------------------------------------------

    def _row_of(self, key: str) -> int | None:
        for row in range(self._list.count()):
            if self._list.item(row).data(KEY_ROLE) == key:
                return row
        return None

    def _set_role(self, key: str, role: int, value: bool) -> None:
        row = self._row_of(key)
        if row is None:
            return
        item = self._list.item(row)
        if bool(item.data(role)) == value:
            return
        item.setData(role, value)
        self.changed.emit()

    def _on_toggled(self, index: QModelIndex, role: int) -> None:
        item = self._list.item(index.row())
        if item is None:
            return
        item.setData(role, not bool(item.data(role)))
        self.changed.emit()

    def _schedule_emit(self, *args) -> None:
        if not self._loading:
            self._emit_timer.start()

    def _emit_if_order_changed(self) -> None:
        order = [s.key for s in self.states()]
        if order != self._last_order:
            self._last_order = order
            self.changed.emit()
