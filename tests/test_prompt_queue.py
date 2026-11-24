from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from ai_mod_painter.core.library import scan_animation
from ai_mod_painter.core.prompt_queue import (
    PHOTO_LAYER,
    PROJECT_DIR,
    QUEUE_DIR,
    destination_for,
    enqueue,
    first_photo_frame,
    list_prompts,
    queue_file_name,
)


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


def test_queue_file_name_is_16_hex_of_sha256_of_both_paths(tmp_path):
    source = tmp_path / "anim" / "frame0" / "render.png"
    template = tmp_path / "prompts" / "convert_autumn.md"
    key = f"{os.path.abspath(source)},{os.path.abspath(template)}"
    expected = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16] + ".md"
    assert queue_file_name(source, template) == expected
    assert len(expected) == 19

    other_frame = tmp_path / "anim" / "frame1" / "render.png"
    other_prompt = tmp_path / "prompts" / "convert_winter.md"
    names = {
        queue_file_name(source, template),
        queue_file_name(other_frame, template),
        queue_file_name(source, other_prompt),
    }
    assert len(names) == 3


def test_enqueue_fills_every_placeholder_and_replaces_the_same_pair(tmp_path):
    template = tmp_path / "convert_summer.md"
    text = (
        "Vstup `{SOURCE_IMAGE}`, výstup `{DESTINATION_IMAGE}`.\r\n"
        "Po uložení `{DESTINATION_IMAGE}` skonči.\n"
    )
    template.write_bytes(text.encode("utf-8"))
    source = tmp_path / "anim" / "frame0" / "render.png"
    queue = tmp_path / "queue"

    first = enqueue(template, source, queue)
    second = enqueue(template, source, queue)

    assert first == second
    assert first.name == queue_file_name(source, template)
    destination = source.with_name("render-photo.png")
    assert first.read_bytes().decode("utf-8") == (
        f"Vstup `{source}`, výstup `{destination}`.\r\nPo uložení `{destination}` skonči.\n"
    )
    assert [p.name for p in queue.iterdir()] == [first.name]  # no temp file, no duplicate


def test_enqueue_missing_template_raises(tmp_path):
    with pytest.raises(OSError):
        enqueue(tmp_path / "missing.md", tmp_path / "render.png", tmp_path / "queue")


def test_photo_layer_is_the_destination_of_render_png():
    assert PHOTO_LAYER == destination_for(Path("render.png")).name == "render-photo.png"


def test_first_photo_frame(make_tree):
    root = make_tree(
        {
            "a/frame0/render.png": None,
            "a/frame1/render.png": None,
            "a/frame2/Render-Photo.PNG": None,
            "a/frame10/render-photo.png": None,
            "b/frame0/render.png": None,
        }
    )
    assert first_photo_frame(scan_animation(root / "a")) == 2
    assert first_photo_frame(scan_animation(root / "b")) is None


def test_queue_dir_is_to_process_in_the_repository():
    assert QUEUE_DIR == PROJECT_DIR / "prompt_queue" / "to_process"


def test_enqueue_creates_the_nested_queue_folder(tmp_path):
    template = tmp_path / "convert.md"
    template.write_text("{SOURCE_IMAGE}", encoding="utf-8")
    queue = tmp_path / "prompt_queue" / "to_process"
    queued = enqueue(template, tmp_path / "render.png", queue)
    assert queued.parent == queue
    assert [p.name for p in queue.iterdir()] == [queued.name]
