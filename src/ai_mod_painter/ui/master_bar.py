"""The bar above the image: panel toggles, Play / Stop, the frame slider, the prompt queue."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QWidget,
)

SLIDER_MAX_WIDTH = 200


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

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMaximumWidth(SLIDER_MAX_WIDTH)
        self.slider.setMinimumWidth(80)
        self.slider.setPageStep(1)
        self.slider.setTracking(True)
        self.slider.valueChanged.connect(self.frame_changed)

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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        layout.addWidget(self.left_toggle)
        layout.addWidget(self.play_button)
        layout.addWidget(self.slider, 1)
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
        for path in prompts:
            self.prompt_combo.addItem(path.stem, path)
        index = self.prompt_combo.findText(keep)
        self.prompt_combo.setCurrentIndex(index if index >= 0 else (0 if prompts else -1))
        self.prompt_combo.blockSignals(False)
        self.prompt_changed.emit()

    def selected_prompt(self) -> Path | None:
        return self.prompt_combo.currentData()

    def set_frames(self, names: list[str]) -> None:
        self._names = list(names)
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
