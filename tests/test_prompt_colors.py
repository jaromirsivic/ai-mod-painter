from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor

from ai_mod_painter.core.prompt_colors import (
    PROMPT_PALETTE,
    UNKNOWN_COLOR,
    color_of,
    prompt_colors,
)

WATCH_ME = ["#FF0000", "#FF8C00", "#FFFF00", "#00C000", "#00E5FF", "#0055FF", "#FF00FF"]


def test_palette_starts_with_watch_me_and_has_no_white_or_black():
    assert list(PROMPT_PALETTE[:7]) == WATCH_ME
    assert len(PROMPT_PALETTE) >= 9
    assert len(set(PROMPT_PALETTE)) == len(PROMPT_PALETTE)
    assert not {"#FFFFFF", "#000000"} & {c.upper() for c in PROMPT_PALETTE}


def test_colors_follow_the_alphabetical_order_of_the_templates():
    prompts = [Path("p/convert_winter.md"), Path("p/convert.md"), Path("p/convert_autumn.md")]
    colors = prompt_colors(prompts)
    assert colors["convert.md"] == QColor(PROMPT_PALETTE[0])
    assert colors["convert_autumn.md"] == QColor(PROMPT_PALETTE[1])
    assert colors["convert_winter.md"] == QColor(PROMPT_PALETTE[2])


def test_more_templates_than_colors_start_again():
    names = [f"p{i:02}.md" for i in range(len(PROMPT_PALETTE) + 1)]
    colors = prompt_colors(names)
    assert colors[names[-1]] == QColor(PROMPT_PALETTE[0])


def test_unknown_prompt_is_gray():
    assert color_of("gone.md", prompt_colors(["a.md"])) == QColor(UNKNOWN_COLOR)


def test_the_repository_templates_get_distinct_colors():
    from ai_mod_painter.core.prompt_queue import PROMPTS_DIR, list_prompts

    prompts = list_prompts(PROMPTS_DIR)
    colors = prompt_colors(prompts)
    assert len({c.name() for c in colors.values()}) == min(len(prompts), len(PROMPT_PALETTE))
