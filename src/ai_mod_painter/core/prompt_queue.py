"""The prompt queue: prompt templates filled with the current frame's ``render.png``.

The templates are the ``*.md`` files in ``assets/prompts`` of the repository. A template
names the input image ``{SOURCE_IMAGE}`` and the output image ``{DESTINATION_IMAGE}``;
both are replaced with absolute paths, and the result is written to
``prompt_queue/prompt-YYYY-MM-DD-HH-MM-SS.md`` for another program to pick up.

This module (with ``layer_presets.py``) is the only place where layer names matter; see
CLAUDE.md.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from ai_mod_painter.core.layer_presets import RENDER_LAYER
from ai_mod_painter.core.library import natural_key

PROJECT_DIR = Path(__file__).resolve().parents[3]
PROMPTS_DIR = PROJECT_DIR / "assets" / "prompts"
QUEUE_DIR = PROJECT_DIR / "prompt_queue"

SOURCE_PLACEHOLDER = "{SOURCE_IMAGE}"
DESTINATION_PLACEHOLDER = "{DESTINATION_IMAGE}"
PROMPT_EXTENSION = ".md"
SOURCE_LAYER = RENDER_LAYER
DESTINATION_SUFFIX = "-photo"


def list_prompts(folder: Path = PROMPTS_DIR) -> list[Path]:
    """The ``*.md`` templates of ``folder``, sorted naturally; empty when it is missing."""
    try:
        with os.scandir(folder) as entries:
            prompts = [
                Path(e.path)
                for e in entries
                if os.path.splitext(e.name)[1].casefold() == PROMPT_EXTENSION and e.is_file()
            ]
    except OSError:
        return []
    prompts.sort(key=lambda p: natural_key(p.name))
    return prompts


def destination_for(source: Path) -> Path:
    """``render.png`` -> ``render-photo.png`` in the same folder."""
    return source.with_name(f"{source.stem}{DESTINATION_SUFFIX}{source.suffix}")


def fill_template(text: str, source: Path, destination: Path) -> str:
    return text.replace(SOURCE_PLACEHOLDER, str(source)).replace(
        DESTINATION_PLACEHOLDER, str(destination)
    )


def queue_file_name(now: datetime, number: int = 1) -> str:
    """``prompt-YYYY-MM-DD-HH-MM-SS.md``; ``-2``, ``-3``, … for more in the same second."""
    base = now.strftime("prompt-%Y-%m-%d-%H-%M-%S")
    suffix = "" if number == 1 else f"-{number}"
    return f"{base}{suffix}{PROMPT_EXTENSION}"


def enqueue(
    template: Path,
    source: Path,
    queue_dir: Path = QUEUE_DIR,
    now: datetime | None = None,
) -> Path:
    """Fill ``template`` for the image ``source`` and write it into ``queue_dir``.

    The file appears atomically (written under a temporary name first). Returns its
    path. Raises ``OSError`` or ``UnicodeDecodeError`` when the template cannot be read
    or the queue file cannot be written.
    """
    source = Path(os.path.abspath(source))
    text = Path(template).read_bytes().decode("utf-8")
    filled = fill_template(text, source, destination_for(source))

    queue_dir = Path(queue_dir)
    queue_dir.mkdir(parents=True, exist_ok=True)
    now = now or datetime.now()
    number = 1
    while (target := queue_dir / queue_file_name(now, number)).exists():
        number += 1
    temp = queue_dir / f".{target.name}.tmp"
    temp.write_bytes(filled.encode("utf-8"))
    os.replace(temp, target)
    return target
