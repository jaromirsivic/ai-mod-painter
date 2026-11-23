"""Decoded images with an LRU memory cap, loaded on background threads."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, QThreadPool, Signal
from PySide6.QtGui import QImage, QImageReader

from ai_mod_painter.core.compositor import WORK_FORMAT

DEFAULT_CAP_BYTES = 1536 * 1024 * 1024  # 1.5 GiB of decoded pixels
DEFAULT_WORKERS = 4


def decode(path: Path) -> QImage:
    """Decode an image in the drawing format; a null image when it cannot be read.

    EXIF orientation is not applied, so the decoded size always equals ``size_of``.
    """
    reader = QImageReader(str(path))
    reader.setAutoTransform(False)
    image = reader.read()
    if image.isNull():
        return image
    return image.convertToFormat(WORK_FORMAT)


class _LoaderSignals(QObject):
    done = Signal(object, QImage)


class _Loader(QRunnable):
    def __init__(self, path: Path, signals: _LoaderSignals) -> None:
        super().__init__()
        self._path = path
        self._signals = signals

    def run(self) -> None:
        self._signals.done.emit(self._path, decode(self._path))


class ImageCache(QObject):
    """LRU cache of decoded images.

    ``request`` replaces the queue of wanted images (first = most urgent); at most
    ``workers`` images decode at once. ``image_loaded`` fires on the GUI thread for every
    finished image, also for one that could not be read (``is_ready`` is then true and
    ``get`` returns ``None``, so a broken file never blocks a frame).
    """

    image_loaded = Signal(object)  # Path

    def __init__(
        self,
        cap_bytes: int = DEFAULT_CAP_BYTES,
        workers: int = DEFAULT_WORKERS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cap = cap_bytes
        self._images: OrderedDict[Path, QImage] = OrderedDict()
        self._bytes = 0
        self._failed: set[Path] = set()
        self._sizes: dict[Path, QSize] = {}
        self._pending: set[Path] = set()
        self._queue: list[Path] = []
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(workers)
        self._signals = _LoaderSignals(self)
        self._signals.done.connect(self._on_done)

    # --- queries -----------------------------------------------------------------------

    @property
    def used_bytes(self) -> int:
        return self._bytes

    def __contains__(self, path: Path) -> bool:
        return path in self._images

    def is_ready(self, path: Path) -> bool:
        return path in self._images or path in self._failed

    def get(self, path: Path) -> QImage | None:
        image = self._images.get(path)
        if image is not None:
            self._images.move_to_end(path)
        return image

    def size_of(self, path: Path) -> QSize:
        """Image size without decoding it (header only); invalid when unreadable."""
        image = self._images.get(path)
        if image is not None:
            return image.size()
        size = self._sizes.get(path)
        if size is None:
            size = QImageReader(str(path)).size()
            self._sizes[path] = size
        return size

    # --- loading -----------------------------------------------------------------------

    def request(self, paths: Iterable[Path]) -> None:
        """Replace the wanted list; images already cached or decoding are skipped."""
        seen: set[Path] = set()
        queue = []
        for path in paths:
            if path in seen or self.is_ready(path) or path in self._pending:
                continue
            seen.add(path)
            queue.append(path)
        self._queue = queue
        self._pump()

    def load_now(self, path: Path) -> QImage | None:
        """Decode synchronously (tests, small tools)."""
        if not self.is_ready(path):
            self._store(path, decode(path))
        return self.get(path)

    def clear(self) -> None:
        self._queue.clear()
        self._images.clear()
        self._bytes = 0
        self._failed.clear()
        self._sizes.clear()

    def shutdown(self) -> None:
        self._queue.clear()
        self._pool.clear()
        self._pool.waitForDone()

    def _pump(self) -> None:
        while self._queue and len(self._pending) < self._pool.maxThreadCount():
            path = self._queue.pop(0)
            if self.is_ready(path) or path in self._pending:
                continue
            self._pending.add(path)
            self._pool.start(_Loader(path, self._signals))

    def _on_done(self, path: Path, image: QImage) -> None:
        self._pending.discard(path)
        self._store(path, image)
        self.image_loaded.emit(path)
        self._pump()

    def _store(self, path: Path, image: QImage) -> None:
        if image.isNull():
            self._failed.add(path)
            return
        old = self._images.pop(path, None)
        if old is not None:
            self._bytes -= old.sizeInBytes()
        self._images[path] = image
        self._bytes += image.sizeInBytes()
        while self._bytes > self._cap and len(self._images) > 1:
            _, evicted = self._images.popitem(last=False)
            self._bytes -= evicted.sizeInBytes()
