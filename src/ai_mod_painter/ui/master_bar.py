"""The bar above the image: panel toggles, Play / Stop, the frame slider, the prompt queue.

The slider shows a short colored vertical line above every frame that has a prompt in
the queue log, in the color of that prompt (see ``core/prompt_colors.py``).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPaintEvent, QPen, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ai_mod_painter.core.prompt_colors import prompt_colors

SLIDER_MAX_WIDTH = 400
MARK_WIDTH = 3
MARK_HEIGHT = 8
MARK_GAP = 2  # between the mark and the slider
SWATCH = 12  # color square in the prompt combo


class MarkedSlider(QSlider):
    """A horizontal slider that keeps marks (value -> color) for ``MarkStrip`` to draw."""

    marks_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._marks: dict[int, QColor] = {}

    def marks(self) -> dict[int, QColor]:
        return dict(self._marks)

    def set_marks(self, marks: dict[int, QColor]) -> None:
        self._marks = {int(value): QColor(color) for value, color in marks.items()}
        self.marks_changed.emit()

    def mark_x(self, value: int) -> int:
        """The x of the handle centre when the slider is at ``value``."""
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        style = self.style()
        groove = style.subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderGroove, self
        )
        handle = style.subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, self
        )
        span = max(groove.width() - handle.width(), 0)
        offset = QStyle.sliderPositionFromValue(
            self.minimum(), self.maximum(), value, span, option.upsideDown
        )
        return groove.left() + handle.width() // 2 + offset

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.marks_changed.emit()

    def sliderChange(self, change: QSlider.SliderChange) -> None:  # noqa: N802
        super().sliderChange(change)
        if change == QSlider.SliderChange.SliderRangeChange:
            self.marks_changed.emit()


class MarkStrip(QWidget):
    """The thin strip right above the slider: one short vertical line per mark."""

    def __init__(self, slider: MarkedSlider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._slider = slider
        self.setFixedHeight(MARK_HEIGHT + MARK_GAP)
        slider.marks_changed.connect(self.update)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        marks = self._slider.marks()
        if not marks:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        offset = self._slider.x() - self.x()  # both share the container's left edge
        for value, color in sorted(marks.items()):
            if not self._slider.minimum() <= value <= self._slider.maximum():
                continue
            pen = QPen(color, MARK_WIDTH)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            x = self._slider.mark_x(value) + offset
            painter.drawLine(QPoint(x, 1), QPoint(x, MARK_HEIGHT - 1))
        painter.end()


def _swatch(color: QColor) -> QIcon:
    pixmap = QPixmap(SWATCH, SWATCH)
    pixmap.fill(color)
    return QIcon(pixmap)


class MasterBar(QWidget):
    frame_changed = Signal(int)
    play_toggled = Signal(bool)
    prompt_changed = Signal()
    add_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.left_toggle = QToolButton()
        self.left_toggle.setText("◧")
        self.left_toggle.setToolTip("Show or hide the animations panel")
        self.left_toggle.setCheckable(True)
        self.right_toggle = QToolButton()
        self.right_toggle.setText("◨")
        self.right_toggle.setToolTip("Show or hide the layers panel")
        self.right_toggle.setCheckable(True)

        self.play_button = QToolButton()
        self.play_button.setCheckable(True)
        self.play_button.setToolTip("Play the frames in a loop at 10 fps (Space)")
        self.play_button.toggled.connect(self._on_play_toggled)

        self.slider = MarkedSlider()
        self.slider.setPageStep(1)
        self.slider.setTracking(True)
        self.slider.valueChanged.connect(self.frame_changed)
        self.mark_strip = MarkStrip(self.slider)

        # Strip above, the same height free below: the slider stays centred in the bar.
        self.slider_box = QWidget()
        self.slider_box.setMaximumWidth(SLIDER_MAX_WIDTH)
        self.slider_box.setMinimumWidth(80)
        box = QVBoxLayout(self.slider_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        box.addWidget(self.mark_strip)
        box.addWidget(self.slider)
        box.addSpacing(MARK_HEIGHT + MARK_GAP)

        self.label = QLabel()
        self.label.setMinimumWidth(120)

        self.prompt_combo = QComboBox()
        self.prompt_combo.setToolTip("Prompt template from assets/prompts")
        self.prompt_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.prompt_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.prompt_combo.currentIndexChanged.connect(lambda _index: self.prompt_changed.emit())
        self.add_button = QPushButton("Add")
        self.add_button.setToolTip(
            "Add the chosen prompt for render.png of this frame to the prompt queue"
        )
        self.add_button.clicked.connect(self.add_clicked)
        self._prompt_colors: dict[str, QColor] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        layout.addWidget(self.left_toggle)
        layout.addWidget(self.play_button)
        layout.addWidget(self.slider_box, 1)
        layout.addWidget(self.label)
        layout.addStretch(1)
        layout.addWidget(self.prompt_combo)
        layout.addWidget(self.add_button)
        layout.addWidget(self.right_toggle)
        self._update_play_text(False)
        self.set_frames([])

    def set_prompts(self, prompts: list[Path], select: str | None = None) -> None:
        """Fill the prompt combo (file names without ``.md``), keeping or choosing ``select``."""
        keep = select if select is not None else self.prompt_combo.currentText()
        self.prompt_combo.blockSignals(True)
        self.prompt_combo.clear()
        self._prompt_colors = prompt_colors(prompts)
        for path in prompts:
            self.prompt_combo.addItem(_swatch(self._prompt_colors[path.name]), path.stem, path)
        index = self.prompt_combo.findText(keep)
        self.prompt_combo.setCurrentIndex(index if index >= 0 else (0 if prompts else -1))
        self.prompt_combo.blockSignals(False)
        self.prompt_changed.emit()

    def selected_prompt(self) -> Path | None:
        return self.prompt_combo.currentData()

    def prompt_colors(self) -> dict[str, QColor]:
        """Template file name -> color, for the templates in the combo."""
        return dict(self._prompt_colors)

    def set_marks(self, marks: dict[int, QColor]) -> None:
        """Frame index -> color of the mark above that frame."""
        self.slider.set_marks(marks)

    def set_frames(self, names: list[str]) -> None:
        self._names = list(names)
        self.slider.set_marks({})
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(len(names) - 1, 0))
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        enabled = bool(names)
        self.slider.setEnabled(enabled)
        self.play_button.setEnabled(enabled)
        if not enabled:
            self.set_playing(False)
        self._update_label(0)

    def set_frame(self, index: int) -> None:
        """Move the slider without emitting ``frame_changed``."""
        self.slider.blockSignals(True)
        self.slider.setValue(index)
        self.slider.blockSignals(False)
        self._update_label(index)

    def frame(self) -> int:
        return self.slider.value()

    def is_playing(self) -> bool:
        return self.play_button.isChecked()

    def set_playing(self, playing: bool) -> None:
        self.play_button.setChecked(playing)

    def _on_play_toggled(self, playing: bool) -> None:
        self._update_play_text(playing)
        self.play_toggled.emit(playing)

    def _update_play_text(self, playing: bool) -> None:
        self.play_button.setText("■" if playing else "▶")

    def _update_label(self, index: int) -> None:
        if not self._names:
            self.label.setText("")
            return
        self.label.setText(f"{self._names[index]}  ({index + 1} / {len(self._names)})")

    def update_label(self) -> None:
        self._update_label(self.slider.value())
