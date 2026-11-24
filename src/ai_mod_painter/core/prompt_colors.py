"""A color for each prompt template, for the marks above the frame slider.

The colors come from ``PROMPT_PALETTE`` in the alphabetical (natural) order of the
templates in ``assets/prompts``; adding or removing a template shifts the colors of the
ones after it. The first seven colors are the Watch Me drawing palette; none is white or
black. More templates than colors start the palette again. A prompt that is no longer
among the templates (only in an old log entry) gets ``UNKNOWN_COLOR``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtGui import QColor

from ai_mod_painter.core.library import natural_key

PROMPT_PALETTE: tuple[str, ...] = (
    "#FF0000",  # red      (Watch Me 1)
    "#FF8C00",  # orange   (Watch Me 2)
    "#FFFF00",  # yellow   (Watch Me 3)
    "#00C000",  # green    (Watch Me 4)
    "#00E5FF",  # cyan     (Watch Me 5)
    "#0055FF",  # blue     (Watch Me 6)
    "#FF00FF",  # magenta  (Watch Me 7)
    "#8A2BE2",  # purple
    "#9AFF3C",  # lime
    "#FF7FB0",  # pink
    "#A0522D",  # brown
    "#00A08A",  # teal
)
UNKNOWN_COLOR = "#9A9A9A"


def prompt_colors(prompts: Sequence[Path | str]) -> dict[str, QColor]:
    """Template file name (``convert_autumn.md``) -> its color."""
    names = sorted({Path(p).name for p in prompts}, key=natural_key)
    return {name: QColor(PROMPT_PALETTE[i % len(PROMPT_PALETTE)]) for i, name in enumerate(names)}


def color_of(name: str, colors: dict[str, QColor]) -> QColor:
    return QColor(colors.get(name, QColor(UNKNOWN_COLOR)))
