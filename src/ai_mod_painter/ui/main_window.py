"""The main window: menu, collapsible side panels, master bar, image view, status line."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QRunnable, QSettings, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QImage, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ai_mod_painter import APP_NAME
from ai_mod_painter.core.compositor import canvas_layer, compose, needed_paths, straight_color
from ai_mod_painter.core.image_cache import ImageCache
from ai_mod_painter.core.layer_state import LayerMemory, LayerState
from ai_mod_painter.core.library import Animation, scan_animation
from ai_mod_painter.ui.animation_panel import AnimationPanel
from ai_mod_painter.ui.image_view import ImageView, format_zoom
from ai_mod_painter.ui.layers_panel import LayersPanel
from ai_mod_painter.ui.master_bar import MasterBar

FPS = 10
FRAME_INTERVAL_MS = 1000 // FPS
PREFETCH_IDLE = 3  # frames on each side of the current one
PREFETCH_PLAYING = 12  # frames ahead while playing (wraps around)


class _TaskSignals(QObject):
    done = Signal(int, object, object)  # token, result, error


class _Task(QRunnable):
    def __init__(self, token: int, fn: Callable[[], object], signals: _TaskSignals) -> None:
        super().__init__()
        self._token = token
        self._fn = fn
        self._signals = signals

    def run(self) -> None:
        try:
            result, error = self._fn(), None
        except Exception as exc:  # reported on the GUI thread
            result, error = None, exc
        self._signals.done.emit(self._token, result, error)


class MainWindow(QMainWindow):
    animation_loaded = Signal()
    frame_shown = Signal(int)

    def __init__(
        self,
        settings: QSettings | None = None,
        cache: ImageCache | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self._settings = settings if settings is not None else QSettings()
        self.cache = cache if cache is not None else ImageCache(parent=self)
        self.cache.image_loaded.connect(self._on_image_loaded)

        self._animation: Animation | None = None
        self._index = 0
        self._shown_index: int | None = None
        self._image: QImage | None = None
        self._fit_pending = False
        self._memory = LayerMemory()
        self._scan_token = 0
        self._scan_pool = QThreadPool(self)
        self._scan_pool.setMaxThreadCount(1)
        self._scan_signals = _TaskSignals(self)
        self._scan_signals.done.connect(self._on_scanned)

        self._build_widgets()
        self._build_menus()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)  # coarse timers drift to ~9 fps
        self._timer.setInterval(FRAME_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

        self._restore_settings()

    # --- construction ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        self.animations = AnimationPanel()
        self.animations.root_opened.connect(self._on_root_opened)
        self.animations.root_failed.connect(self._show_error)
        self.animations.animation_selected.connect(self.open_animation)

        self.master = MasterBar()
        self.master.frame_changed.connect(self.set_frame)
        self.master.play_toggled.connect(self._on_play_toggled)

        self.view = ImageView()
        self.view.zoom_changed.connect(self._on_zoom_changed)
        self.view.hover_changed.connect(self._on_hover_changed)

        self.size_label = QLabel()
        self.zoom_label = QLabel()
        self.pixel_label = QLabel()
        self.message_label = QLabel()
        self.message_label.setStyleSheet("color: #c0392b;")
        status = QHBoxLayout()
        status.setContentsMargins(6, 2, 6, 2)
        status.setSpacing(16)
        for label in (self.size_label, self.zoom_label, self.pixel_label):
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            status.addWidget(label)
        status.addWidget(self.message_label, 1)
        status_bar = QWidget()
        status_bar.setLayout(status)
        status_bar.setObjectName("statusLine")

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self.master)
        center_layout.addWidget(self.view, 1)
        center_layout.addWidget(status_bar)

        self.layers = LayersPanel()
        self.layers.changed.connect(self._on_layers_changed)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.animations)
        self.splitter.addWidget(center)
        self.splitter.addWidget(self.layers)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([280, 900, 260])
        self.splitter.splitterMoved.connect(self._sync_panel_actions)
        self.setCentralWidget(self.splitter)
        self._on_zoom_changed(self.view.zoom())

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = QAction("&Open folder…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.animations.browse)
        file_menu.addAction(open_action)
        reload_action = QAction("&Reload", self)
        reload_action.setShortcut(QKeySequence(Qt.Key.Key_F5))
        reload_action.triggered.connect(self.reload)
        file_menu.addAction(reload_action)
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = self.menuBar().addMenu("&View")
        self.show_animations_action = QAction("Show &animations panel", self)
        self.show_animations_action.setCheckable(True)
        self.show_animations_action.setChecked(True)
        self.show_animations_action.toggled.connect(
            lambda on: self.set_panel_visible(self.animations, on)
        )
        self.show_layers_action = QAction("Show &layers panel", self)
        self.show_layers_action.setCheckable(True)
        self.show_layers_action.setChecked(True)
        self.show_layers_action.toggled.connect(lambda on: self.set_panel_visible(self.layers, on))
        view_menu.addAction(self.show_animations_action)
        view_menu.addAction(self.show_layers_action)
        view_menu.addSeparator()
        fit_action = QAction("Zoom to &fit", self)
        fit_action.setShortcut(QKeySequence(Qt.Key.Key_F))
        fit_action.triggered.connect(self.view.fit)
        actual_action = QAction("&100 %", self)
        actual_action.setShortcut(QKeySequence(Qt.Key.Key_1))
        actual_action.triggered.connect(self.view.actual_size)
        view_menu.addAction(fit_action)
        view_menu.addAction(actual_action)

        play_menu = self.menuBar().addMenu("&Playback")
        self.play_action = QAction("&Play / Stop", self)
        self.play_action.setShortcut(QKeySequence(Qt.Key.Key_Space))
        self.play_action.triggered.connect(self.toggle_play)
        play_menu.addAction(self.play_action)
        prev_action = QAction("P&revious frame", self)
        prev_action.setShortcut(QKeySequence(Qt.Key.Key_Comma))
        prev_action.triggered.connect(lambda: self.step(-1))
        next_action = QAction("&Next frame", self)
        next_action.setShortcut(QKeySequence(Qt.Key.Key_Period))
        next_action.triggered.connect(lambda: self.step(1))
        play_menu.addAction(prev_action)
        play_menu.addAction(next_action)

        self.master.left_toggle.setChecked(True)
        self.master.right_toggle.setChecked(True)
        self.master.left_toggle.toggled.connect(self.show_animations_action.setChecked)
        self.master.right_toggle.toggled.connect(self.show_layers_action.setChecked)
        self.show_animations_action.toggled.connect(self.master.left_toggle.setChecked)
        self.show_layers_action.toggled.connect(self.master.right_toggle.setChecked)

    # --- panels ------------------------------------------------------------------------

    def set_panel_visible(self, panel: QWidget, visible: bool) -> None:
        index = self.splitter.indexOf(panel)
        if visible:
            panel.show()
            sizes = self.splitter.sizes()
            if sizes[index] == 0:
                sizes[index] = 260
                self.splitter.setSizes(sizes)
        else:
            panel.hide()

    def panel_visible(self, panel: QWidget) -> bool:
        return panel.isVisibleTo(self) and self.splitter.sizes()[self.splitter.indexOf(panel)] > 0

    def _sync_panel_actions(self, *_args) -> None:
        sizes = self.splitter.sizes()
        for panel, action in (
            (self.animations, self.show_animations_action),
            (self.layers, self.show_layers_action),
        ):
            shown = sizes[self.splitter.indexOf(panel)] > 0
            if action.isChecked() != shown:
                action.blockSignals(True)
                action.setChecked(shown)
                action.blockSignals(False)
                toggle = (
                    self.master.left_toggle
                    if panel is self.animations
                    else self.master.right_toggle
                )
                toggle.blockSignals(True)
                toggle.setChecked(shown)
                toggle.blockSignals(False)
                if not shown:
                    panel.hide()

    # --- root and animation ------------------------------------------------------------

    def open_root(self, root: Path) -> bool:
        return self.animations.open_root(Path(root))

    def _on_root_opened(self, root: Path) -> None:
        self._settings.setValue("root", str(root))
        self._close_animation()
        self.message_label.setText("")
        if not self.animations.animations:
            self.view.set_message("No animation folders in this folder")
        else:
            self.view.set_message("Choose an animation on the left")

    def _close_animation(self) -> None:
        self.stop()
        if self._animation is not None:
            self._memory.remember(self.layers.states())
        self._scan_token += 1
        self._animation = None
        self._index = 0
        self._shown_index = None
        self._image = None
        self.master.set_frames([])
        self.layers.set_layers([])
        self.view.set_image(None)
        self._update_status()

    def open_animation(self, path: Path) -> None:
        """Scan the animation on a worker thread, then show its first frame."""
        self.stop()
        self._scan_token += 1
        token = self._scan_token
        self.view.set_message(f"Loading {Path(path).name}…")
        self._scan_pool.start(_Task(token, lambda: scan_animation(Path(path)), self._scan_signals))

    def reload(self) -> None:
        """F5: list the root again and rescan the open animation (new frames and files)."""
        self.animations.reload_root()
        if self._animation is not None:
            self._scan_token += 1
            token = self._scan_token
            path = self._animation.path
            self._scan_pool.start(_Task(token, lambda: scan_animation(path), self._scan_signals))

    def _on_scanned(self, token: int, animation: Animation | None, error: Exception | None) -> None:
        if token != self._scan_token:
            return
        if error is not None or animation is None:
            self._close_animation()
            self._show_error(f"Cannot read the animation: {error}")
            self.view.set_message("Cannot read this animation")
            return

        reloading = self._animation is not None and self._animation.path == animation.path
        if self._animation is not None:
            self._memory.remember(self.layers.states())
        previous_frame = self._animation.frames[self._index].name if reloading else None

        self._animation = animation
        self.message_label.setText("")
        states = self._memory.apply(animation.layers)
        counts = {layer.key: layer.frame_count for layer in animation.layers}
        self.layers.set_layers(states, counts, len(animation.frames))
        self.master.set_frames([f.name for f in animation.frames])
        self._shown_index = None

        if not animation.frames:
            self.stop()
            self._image = None
            self.view.set_image(None)
            self.view.set_message("No images in this animation")
            self._update_status()
            self.animation_loaded.emit()
            return

        index = 0
        if previous_frame is not None:
            names = [f.name for f in animation.frames]
            if previous_frame in names:
                index = names.index(previous_frame)
        self._fit_pending = not reloading
        self.view.set_message("")
        self._index = -1
        self.set_frame(index)
        self.animation_loaded.emit()

    @property
    def animation(self) -> Animation | None:
        return self._animation

    # --- frames ------------------------------------------------------------------------

    @property
    def frame_index(self) -> int:
        return self._index

    @property
    def shown_index(self) -> int | None:
        return self._shown_index

    @property
    def image(self) -> QImage | None:
        """The composed image on screen."""
        return self._image

    def set_frame(self, index: int) -> None:
        if self._animation is None or not self._animation.frames:
            return
        index = min(max(index, 0), len(self._animation.frames) - 1)
        if index == self._index and self._shown_index == index:
            return
        self._index = index
        self.master.set_frame(index)
        self._refresh()

    def step(self, delta: int) -> None:
        if self._animation is None or not self._animation.frames:
            return
        self.set_frame((self._index + delta) % len(self._animation.frames))

    def _refresh(self) -> None:
        """Show the current frame once its images are decoded; until then keep the old one."""
        if self._animation is None or not self._animation.frames:
            return
        frame = self._animation.frames[self._index]
        states = self.layers.states()
        self.layers.set_present(frame.files.keys())
        needed = needed_paths(frame, states)
        self.cache.request(needed + self._prefetch_paths(states))
        if any(not self.cache.is_ready(path) for path in needed):
            return

        image = compose(frame, states, self.cache.get, self.cache.size_of)
        self._image = image
        self.view.set_image(image)
        if self._fit_pending and image is not None:
            self._fit_pending = False
            self.view.fit()
        self._shown_index = self._index
        self._update_status()
        self.frame_shown.emit(self._index)

    def _prefetch_paths(self, states: list[LayerState]) -> list:
        assert self._animation is not None
        frames = self._animation.frames
        count = len(frames)
        if self.is_playing():
            offsets = list(range(1, min(PREFETCH_PLAYING, count - 1) + 1))
        else:
            offsets = []
            for distance in range(1, PREFETCH_IDLE + 1):
                offsets += [distance, -distance]
        paths = []
        seen = set()
        for offset in offsets:
            i = (self._index + offset) % count if self.is_playing() else self._index + offset
            if not 0 <= i < count or i in seen or i == self._index:
                continue
            seen.add(i)
            paths += needed_paths(frames[i], states)
        return paths

    def _on_image_loaded(self, path: Path) -> None:
        if self._animation is None or not self._animation.frames:
            return
        if self._shown_index == self._index:
            return  # current frame already shown; this was a prefetch
        frame = self._animation.frames[self._index]
        if path in frame.files.values():
            self._refresh()

    def _on_layers_changed(self) -> None:
        if self._animation is None:
            return
        self._shown_index = None
        self._refresh()

    # --- playback ----------------------------------------------------------------------

    def is_playing(self) -> bool:
        return self._timer.isActive()

    def toggle_play(self) -> None:
        self.master.set_playing(not self.master.is_playing())

    def play(self) -> None:
        self.master.set_playing(True)

    def stop(self) -> None:
        self.master.set_playing(False)

    def _on_play_toggled(self, playing: bool) -> None:
        if playing and self._animation is not None and self._animation.frames:
            self._timer.start()
        else:
            self._timer.stop()
            if self.master.is_playing():
                self.master.set_playing(False)

    def _on_tick(self) -> None:
        if self._animation is None or not self._animation.frames:
            self.stop()
            return
        if self.master.slider.isSliderDown():
            return  # the user holds the slider: continue from there after release
        if self._shown_index != self._index:
            return  # the current frame is still decoding: hold it, never skip
        self.set_frame((self._index + 1) % len(self._animation.frames))

    # --- status ------------------------------------------------------------------------

    def _update_status(self) -> None:
        if self._image is not None and self._animation is not None:
            frame = self._animation.frames[self._index]
            base = canvas_layer(frame, self.layers.states())
            name = f" ({base.name})" if base is not None else ""
            self.size_label.setText(f"{self._image.width()} x {self._image.height()}{name}")
        else:
            self.size_label.setText("")
        self._on_hover_changed(self.view.hover_point())

    def _on_zoom_changed(self, zoom: float) -> None:
        self.zoom_label.setText(format_zoom(zoom))

    def _on_hover_changed(self, point: QPoint | None) -> None:
        image = self._image
        if point is None or image is None or not image.rect().contains(point):
            self.pixel_label.setText("")
            return
        color = straight_color(image, point.x(), point.y())
        self.pixel_label.setText(
            f"{point.x()},{point.y()}  #{color.red():02X}{color.green():02X}"
            f"{color.blue():02X}{color.alpha():02X}"
        )

    def _show_error(self, message: str) -> None:
        self.message_label.setText(message)

    # --- settings ----------------------------------------------------------------------

    def _restore_settings(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(1440, 900)
        splitter = self._settings.value("splitter")
        if splitter is not None:
            self.splitter.restoreState(splitter)
        self.show_animations_action.setChecked(
            self._settings.value("show_animations", True, type=bool)
        )
        self.show_layers_action.setChecked(self._settings.value("show_layers", True, type=bool))

    def restore_root(self) -> None:
        root = self._settings.value("root", "", type=str)
        if root and Path(root).is_dir():
            self.open_root(Path(root))
        else:
            self.view.set_message("Open a folder with animations (File → Open folder…)")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.stop()
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("splitter", self.splitter.saveState())
        self._settings.setValue("show_animations", self.show_animations_action.isChecked())
        self._settings.setValue("show_layers", self.show_layers_action.isChecked())
        self._scan_pool.clear()
        self._scan_pool.waitForDone()
        self.cache.shutdown()
        super().closeEvent(event)
