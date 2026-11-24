"""Left panel: root folder path, Reload / Photo / Delete Selected, the animations, the pager.

Animations are listed 100 per page. Each row has a thumbs-up icon (approve: the row
turns green and ``ai-mod-config.json`` is written into the animation folder) and, as the
last item, a trash icon (mark for deletion: the row turns red, nothing is deleted until
Delete Selected). Rows are gray otherwise. Both icons are switches and the last one
wins: marking an approved row takes the approval back, approving a marked row removes
the mark. Deletion marks are kept in memory only.

Photo is a toggle (off at every start): while it is on, the main window shows the
first frame with a processed photo of every animation it opens.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QModelIndex, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_mod_painter.core.library import PAGE_SIZE, list_animations, page, page_count
from ai_mod_painter.core.review import read_approved, write_approved

PATH_ROLE = Qt.ItemDataRole.UserRole + 1
APPROVED_ROLE = Qt.ItemDataRole.UserRole + 2
MARKED_ROLE = Qt.ItemDataRole.UserRole + 3

ROW_HEIGHT = 26
ICON = 18
TRASH_RIGHT = 4  # gap between the trash icon and the row's right edge
ICON_GAP = 6

GRAY = QColor(128, 128, 128, 45)
GREEN = QColor(46, 160, 67, 120)
RED = QColor(210, 45, 45, 130)


def trash_rect(row: QRect) -> QRect:
    return QRect(row.right() - TRASH_RIGHT - ICON + 1, row.center().y() - ICON // 2, ICON, ICON)


def thumb_rect(row: QRect) -> QRect:
    trash = trash_rect(row)
    return QRect(trash.left() - ICON_GAP - ICON, trash.top(), ICON, ICON)


def _thumb_path(r: QRectF) -> QPainterPath:
    """A thumbs-up drawn in a 16 x 16 box: the cuff on the left, the hand on the right."""

    def p(x: float, y: float) -> QPointF:
        return QPointF(r.left() + x * r.width() / 16, r.top() + y * r.height() / 16)

    path = QPainterPath()
    path.addRect(QRectF(p(0.5, 7), p(3.5, 15.5)))
    path.moveTo(p(5, 15.5))
    path.lineTo(p(5, 7.5))
    path.lineTo(p(8, 4.5))
    path.lineTo(p(8.8, 1))
    path.quadTo(p(11.5, 0.8), p(10.8, 4))
    path.lineTo(p(10.2, 6.5))
    path.lineTo(p(14.2, 6.5))
    path.quadTo(p(16, 6.6), p(15.6, 8.6))
    path.lineTo(p(14.4, 14.2))
    path.quadTo(p(14, 15.5), p(12.6, 15.5))
    path.closeSubpath()
    return path


def _trash_path(r: QRectF) -> QPainterPath:
    """A trash can drawn in a 16 x 16 box: handle, lid and a tapered body."""

    def p(x: float, y: float) -> QPointF:
        return QPointF(r.left() + x * r.width() / 16, r.top() + y * r.height() / 16)

    path = QPainterPath()
    path.addRect(QRectF(p(6, 1), p(10, 2.5)))
    path.addRect(QRectF(p(1.5, 2.5), p(14.5, 4.5)))
    path.moveTo(p(3, 5.5))
    path.lineTo(p(4, 15.5))
    path.lineTo(p(12, 15.5))
    path.lineTo(p(13, 5.5))
    path.closeSubpath()
    return path


class _AnimationDelegate(QStyledItemDelegate):
    approve_clicked = Signal(QModelIndex)
    mark_clicked = Signal(QModelIndex)

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        size = super().sizeHint(option, index)
        return QSize(size.width() + 2 * ICON + ICON_GAP + 8, max(size.height(), ROW_HEIGHT))

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        approved = bool(index.data(APPROVED_ROLE))
        marked = bool(index.data(MARKED_ROLE))
        row = option.rect

        painter.save()
        painter.fillRect(row.adjusted(0, 1, 0, -1), RED if marked else GREEN if approved else GRAY)
        painter.restore()

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style is not None:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        palette = opt.palette
        color = palette.highlightedText().color() if selected else palette.text().color()
        painter.setPen(color)
        trash = trash_rect(row)
        first_icon = thumb_rect(row)
        text_width = first_icon.left() - row.left() - 10
        text_rect = QRect(row.left() + 6, row.top(), text_width, row.height())
        elided = opt.fontMetrics.elidedText(text, Qt.TextElideMode.ElideMiddle, text_rect.width())
        align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        painter.drawText(text_rect, align, elided)

        self._paint_icon(painter, _trash_path(QRectF(trash).adjusted(1, 1, -1, -1)), marked, opt)
        thumb = QRectF(thumb_rect(row)).adjusted(1, 1, -1, -1)
        self._paint_icon(painter, _thumb_path(thumb), approved, opt)
        painter.restore()

    @staticmethod
    def _paint_icon(painter: QPainter, path: QPainterPath, active: bool, opt) -> None:
        color = opt.palette.text().color()
        if active:
            painter.setPen(QPen(color, 1.2))
            painter.setBrush(color)
        else:
            color.setAlphaF(0.55)
            painter.setPen(QPen(color, 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

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
        targets = (
            (thumb_rect(option.rect), self.approve_clicked),
            (trash_rect(option.rect), self.mark_clicked),
        )
        for rect, signal in targets:
            if rect.adjusted(-2, -2, 2, 2).contains(pos):
                if event.type() == QEvent.Type.MouseButtonRelease:
                    signal.emit(index)
                return True  # also swallow press / double click: the selection stays
        return super().editorEvent(event, model, option, index)


class AnimationPanel(QWidget):
    root_opened = Signal(object)  # Path
    error = Signal(str)  # message for the status line
    animation_selected = Signal(object)  # Path
    reload_clicked = Signal()
    delete_clicked = Signal()
    photo_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root: Path | None = None
        self._animations: list[Path] = []
        self._marked: set[Path] = set()
        self._page = 0

        self._path = QLineEdit()
        self._path.setPlaceholderText("Folder with animations…")
        self._path.setClearButtonEnabled(True)
        self._path.returnPressed.connect(self._on_path_entered)
        self._browse = QToolButton()
        self._browse.setText("…")
        self._browse.setToolTip("Choose the folder with animations")
        self._browse.clicked.connect(self.browse)

        path_row = QHBoxLayout()
        path_row.setSpacing(4)
        path_row.addWidget(self._path, 1)
        path_row.addWidget(self._browse)

        self.reload_button = QPushButton("Reload")
        self.reload_button.setToolTip(
            "List the folder again, clear the deletion marks and go to page 1"
        )
        self.reload_button.clicked.connect(self.reload_clicked)
        self.photo_button = QPushButton("Photo")
        self.photo_button.setCheckable(True)
        self.photo_button.setToolTip(
            "While pressed, every animation opens at its first frame with render-photo.png"
        )
        self.photo_button.toggled.connect(self.photo_toggled)
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setToolTip("Permanently delete the animations marked with the trash")
        self.delete_button.clicked.connect(self.delete_clicked)

        button_row = QHBoxLayout()
        button_row.setSpacing(4)
        button_row.addWidget(self.reload_button)
        button_row.addWidget(self.photo_button)
        button_row.addWidget(self.delete_button)

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
        self._list.setMouseTracking(True)
        self._delegate = _AnimationDelegate(self._list)
        self._list.setItemDelegate(self._delegate)
        self._delegate.approve_clicked.connect(lambda index: self._on_approve_clicked(index))
        self._delegate.mark_clicked.connect(lambda index: self._on_mark_clicked(index))
        self._list.currentItemChanged.connect(self._on_current_changed)

        self._prev = QToolButton()
        self._prev.setText("‹")
        self._prev.setToolTip("Previous page")
        self._prev.clicked.connect(lambda: self.set_page(self._page - 1))
        self._next = QToolButton()
        self._next.setText("›")
        self._next.setToolTip("Next page")
        self._next.clicked.connect(lambda: self.set_page(self._page + 1))
        self._page_label = QLabel()
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pager = QHBoxLayout()
        pager.setSpacing(4)
        pager.addWidget(self._prev)
        pager.addWidget(self._page_label, 1)
        pager.addWidget(self._next)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addLayout(path_row)
        layout.addLayout(button_row)
        layout.addWidget(self._list, 1)
        layout.addLayout(pager)
        self._update_pager()
        self._update_buttons()

    # --- state -------------------------------------------------------------------------

    @property
    def root(self) -> Path | None:
        return self._root

    @property
    def animations(self) -> list[Path]:
        return list(self._animations)

    @property
    def current_page(self) -> int:
        return self._page

    @property
    def list_widget(self) -> QListWidget:
        return self._list

    def page_total(self) -> int:
        return page_count(len(self._animations))

    def visible_animations(self) -> list[Path]:
        return [self._list.item(i).data(PATH_ROLE) for i in range(self._list.count())]

    def is_approved(self, path: Path) -> bool:
        item = self._item_of(path)
        return item is not None and bool(item.data(APPROVED_ROLE))

    def is_photo_on(self) -> bool:
        return self.photo_button.isChecked()

    def is_marked(self, path: Path) -> bool:
        return Path(path) in self._marked

    def marked_animations(self) -> list[Path]:
        """The animations marked for deletion (on every page), in list order."""
        return [p for p in self._animations if p in self._marked]

    # --- actions -----------------------------------------------------------------------

    def browse(self) -> None:
        start = str(self._root) if self._root else self._path.text()
        chosen = QFileDialog.getExistingDirectory(self, "Choose the folder with animations", start)
        if chosen:
            self.open_root(Path(chosen))

    def open_root(self, root: Path) -> bool:
        root = Path(root)
        self._path.setText(str(root))
        try:
            animations = list_animations(root)
        except OSError as error:
            self.error.emit(f"Cannot open {root}: {error.strerror or error}")
            return False
        self._root = root
        self._animations = animations
        self._marked.clear()
        self._page = 0
        self._fill()
        self.root_opened.emit(root)
        return True

    def reload_root(self) -> None:
        """F5: list the root again (new animations), keeping the page, selection and marks."""
        if self._root is None:
            return
        current = self.selected_animation()
        page_index = self._page
        try:
            self._animations = list_animations(self._root)
        except OSError as error:
            self.error.emit(f"Cannot open {self._root}: {error.strerror or error}")
            return
        self._marked &= set(self._animations)
        self._page = min(page_index, self.page_total() - 1)
        self._fill(select=current)

    def reload_all(self) -> None:
        """The Reload button: list the root again, clear the marks, go to page 1."""
        if self._root is None:
            return
        current = self.selected_animation()
        try:
            self._animations = list_animations(self._root)
        except OSError as error:
            self.error.emit(f"Cannot open {self._root}: {error.strerror or error}")
            return
        self._marked.clear()
        self._page = 0
        self._fill(select=current)

    def set_page(self, index: int) -> None:
        index = min(max(index, 0), self.page_total() - 1)
        if index == self._page:
            return
        self._page = index
        self._fill()

    def selected_animation(self) -> Path | None:
        item = self._list.currentItem()
        return item.data(PATH_ROLE) if item is not None else None

    def select_row(self, row: int) -> None:
        self._list.setCurrentRow(row)

    def toggle_approved(self, path: Path) -> None:
        """Thumbs-up / A: approve or un-approve; approving removes a deletion mark."""
        path = Path(path)
        item = self._item_of(path)
        if item is None:
            return
        approved = not bool(item.data(APPROVED_ROLE))
        if not self._write_approval(item, approved):
            return
        if approved:
            self._set_marked(path, False)

    def approve(self, path: Path) -> bool:
        """S: approve (never take an approval back) and remove a deletion mark.

        An approved row is left as it is, so its file and time stay untouched. Returns
        ``False`` when the approval cannot be written or the row is not on this page.
        """
        path = Path(path)
        item = self._item_of(path)
        if item is None:
            return False
        if not bool(item.data(APPROVED_ROLE)) and not self._write_approval(item, True):
            return False
        self._set_marked(path, False)
        return True

    def toggle_marked(self, path: Path) -> None:
        """Trash / D: mark or unmark for deletion; marking takes an approval back."""
        path = Path(path)
        marked = not self.is_marked(path)
        item = self._item_of(path)
        if marked and item is not None and bool(item.data(APPROVED_ROLE)):
            if not self._write_approval(item, False):
                return
        self._set_marked(path, marked)

    def toggle_approved_selected(self) -> None:
        path = self.selected_animation()
        if path is not None:
            self.toggle_approved(path)

    def approve_selected(self) -> bool:
        path = self.selected_animation()
        return path is not None and self.approve(path)

    def toggle_marked_selected(self) -> None:
        path = self.selected_animation()
        if path is not None:
            self.toggle_marked(path)

    def select_next(self, delta: int) -> None:
        """↑ / ↓: the previous / next animation, across pages, stopping at both ends.

        With no row selected, ↓ selects the first row of the page and ↑ the last.
        """
        count = self._list.count()
        if count == 0 or delta == 0:
            return
        row = self._list.currentRow()
        if row < 0:
            target = 0 if delta > 0 else count - 1
        else:
            target = row + delta
        if target < 0:
            if self._page == 0:
                return
            self.set_page(self._page - 1)
            target = self._list.count() - 1
        elif target >= count:
            if self._page >= self.page_total() - 1:
                return
            self.set_page(self._page + 1)
            target = 0
        self._list.setCurrentRow(target)
        self._list.scrollToItem(self._list.item(target))

    # --- internals ---------------------------------------------------------------------

    def _write_approval(self, item: QListWidgetItem, approved: bool) -> bool:
        path = item.data(PATH_ROLE)
        try:
            write_approved(path, approved)
        except OSError as error:
            self.error.emit(f"Cannot write the approval of {path.name}: {error.strerror or error}")
            return False
        item.setData(APPROVED_ROLE, approved)
        return True

    def _item_of(self, path: Path) -> QListWidgetItem | None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(PATH_ROLE) == Path(path):
                return item
        return None

    def _set_marked(self, path: Path, marked: bool) -> None:
        path = Path(path)
        if marked:
            self._marked.add(path)
        else:
            self._marked.discard(path)
        item = self._item_of(path)
        if item is not None:
            item.setData(MARKED_ROLE, marked)
        self._update_buttons()

    def _on_approve_clicked(self, index: QModelIndex) -> None:
        item = self._list.item(index.row())
        if item is not None:
            self.toggle_approved(item.data(PATH_ROLE))

    def _on_mark_clicked(self, index: QModelIndex) -> None:
        item = self._list.item(index.row())
        if item is not None:
            self.toggle_marked(item.data(PATH_ROLE))

    def _on_path_entered(self) -> None:
        text = self._path.text().strip().strip('"')
        if text:
            self.open_root(Path(text))

    def _fill(self, select: Path | None = None) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for path in page(self._animations, self._page, PAGE_SIZE):
            item = QListWidgetItem(path.name)
            item.setData(PATH_ROLE, path)
            item.setData(APPROVED_ROLE, read_approved(path))
            item.setData(MARKED_ROLE, path in self._marked)
            item.setToolTip(str(path))
            self._list.addItem(item)
            if select is not None and path == select:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)
        self._update_pager()
        self._update_buttons()

    def _update_pager(self) -> None:
        total = len(self._animations)
        pages = self.page_total()
        self._page_label.setText(
            f"page {self._page + 1} / {pages} · {total} animation{'s' if total != 1 else ''}"
        )
        self._prev.setEnabled(self._page > 0)
        self._next.setEnabled(self._page < pages - 1)

    def _update_buttons(self) -> None:
        self.reload_button.setEnabled(self._root is not None)
        count = len(self._marked)
        self.delete_button.setEnabled(count > 0)
        self.delete_button.setText(f"Delete Selected ({count})" if count else "Delete Selected")

    def _on_current_changed(self, current: QListWidgetItem | None, _previous) -> None:
        if current is not None:
            self.animation_selected.emit(current.data(PATH_ROLE))
