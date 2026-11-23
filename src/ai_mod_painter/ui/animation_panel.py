"""Left panel: root folder path, the animation folders (100 per page), the pager."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_mod_painter.core.library import PAGE_SIZE, list_animations, page, page_count

PATH_ROLE = Qt.ItemDataRole.UserRole + 1


class AnimationPanel(QWidget):
    root_opened = Signal(object)  # Path
    root_failed = Signal(str)  # message
    animation_selected = Signal(object)  # Path

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._root: Path | None = None
        self._animations: list[Path] = []
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

        self._list = QListWidget()
        self._list.setUniformItemSizes(True)
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
        layout.addWidget(self._list, 1)
        layout.addLayout(pager)
        self._update_pager()

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
            self.root_failed.emit(f"Cannot open {root}: {error.strerror or error}")
            return False
        self._root = root
        self._animations = animations
        self._page = 0
        self._fill()
        self.root_opened.emit(root)
        return True

    def reload_root(self) -> None:
        """List the root again (new animations), keeping the page and the selection."""
        if self._root is None:
            return
        current = self.selected_animation()
        page_index = self._page
        try:
            self._animations = list_animations(self._root)
        except OSError as error:
            self.root_failed.emit(f"Cannot open {self._root}: {error.strerror or error}")
            return
        self._page = min(page_index, self.page_total() - 1)
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

    # --- internals ---------------------------------------------------------------------

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
            item.setToolTip(str(path))
            self._list.addItem(item)
            if select is not None and path == select:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)
        self._update_pager()

    def _update_pager(self) -> None:
        total = len(self._animations)
        pages = self.page_total()
        self._page_label.setText(
            f"page {self._page + 1} / {pages} · {total} animation{'s' if total != 1 else ''}"
        )
        self._prev.setEnabled(self._page > 0)
        self._next.setEnabled(self._page < pages - 1)

    def _on_current_changed(self, current: QListWidgetItem | None, _previous) -> None:
        if current is not None:
            self.animation_selected.emit(current.data(PATH_ROLE))
