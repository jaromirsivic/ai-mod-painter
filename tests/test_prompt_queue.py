from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from ai_mod_painter.core.prompt_queue import (
    PROJECT_DIR,
    destination_for,
    enqueue,
    list_prompts,
    queue_file_name,
)

NOW = datetime(2026, 11, 24, 7, 5, 9)


def test_project_dir_is_the_repository():
    assert (PROJECT_DIR / "pyproject.toml").is_file()


def test_list_prompts_sorted_naturally_md_only(tmp_path):
    for name in ("b10.md", "b2.md", "a.MD", "notes.txt"):
        (tmp_path / name).write_text("", encoding="utf-8")
    (tmp_path / "folder.md").mkdir()
    assert [p.name for p in list_prompts(tmp_path)] == ["a.MD", "b2.md", "b10.md"]
    assert list_prompts(tmp_path / "missing") == []


def test_destination_adds_photo_to_the_stem():
    assert destination_for(Path("D:/r/frame0/render.png")) == Path("D:/r/frame0/render-photo.png")


def test_queue_file_name():
    assert queue_file_name(NOW) == "prompt-2026-11-24-07-05-09.md"
    assert queue_file_name(NOW, 3) == "prompt-2026-11-24-07-05-09-3.md"


def test_enqueue_fills_every_placeholder_and_keeps_the_text(tmp_path):
    template = tmp_path / "convert_summer.md"
    text = (
        "Vstup `{SOURCE_IMAGE}`, výstup `{DESTINATION_IMAGE}`.\r\n"
        "Po uložení `{DESTINATION_IMAGE}` skonči.\n"
    )
    template.write_bytes(text.encode("utf-8"))
    source = tmp_path / "anim" / "frame0" / "render.png"
    queue = tmp_path / "queue"

    first = enqueue(template, source, queue, now=NOW)
    second = enqueue(template, source, queue, now=NOW)

    assert first.name == "prompt-2026-11-24-07-05-09.md"
    assert second.name == "prompt-2026-11-24-07-05-09-2.md"
    destination = source.with_name("render-photo.png")
    assert first.read_bytes().decode("utf-8") == (
        f"Vstup `{source}`, výstup `{destination}`.\r\nPo uložení `{destination}` skonči.\n"
    )
    assert {p.name for p in queue.iterdir()} == {first.name, second.name}  # no temp file


def test_enqueue_missing_template_raises(tmp_path):
    with pytest.raises(OSError):
        enqueue(tmp_path / "missing.md", tmp_path / "render.png", tmp_path / "queue", now=NOW)
