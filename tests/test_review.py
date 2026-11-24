from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta

import pytest

from ai_mod_painter.core.review import (
    CONFIG_NAME,
    append_prompt_record,
    delete_folder,
    read_approved,
    timestamp,
    write_approved,
)

NOW = datetime(2026, 11, 24, 6, 35, 12, 345000)


def test_missing_or_broken_config_is_not_approved(tmp_path):
    assert not read_approved(tmp_path)
    (tmp_path / CONFIG_NAME).write_text("{not json", encoding="utf-8")
    assert not read_approved(tmp_path)
    (tmp_path / CONFIG_NAME).write_text("[true]", encoding="utf-8")
    assert not read_approved(tmp_path)
    (tmp_path / CONFIG_NAME).write_text('{"approved": "yes"}', encoding="utf-8")
    assert not read_approved(tmp_path)


def read(folder):
    return json.loads((folder / CONFIG_NAME).read_text(encoding="utf-8"))


def test_write_and_read_back_with_the_time_keeping_other_keys(tmp_path):
    (tmp_path / CONFIG_NAME).write_text('{"note": "keep me"}', encoding="utf-8")
    write_approved(tmp_path, True, now=NOW)
    assert read_approved(tmp_path)
    assert read(tmp_path) == {
        "note": "keep me",
        "approved": True,
        "approved_changed_at": timestamp(NOW),
    }

    later = NOW + timedelta(minutes=5)
    write_approved(tmp_path, False, now=later)
    assert not read_approved(tmp_path)
    assert read(tmp_path)["approved_changed_at"] == timestamp(later)
    assert sorted(p.name for p in tmp_path.iterdir()) == [CONFIG_NAME]  # no temp file left


def test_timestamp_is_local_iso_with_offset_to_the_second():
    text = timestamp(NOW)
    assert text.startswith("2026-11-24T06:35:12")
    assert datetime.fromisoformat(text).utcoffset() is not None


def test_prompt_records_are_appended(tmp_path):
    write_approved(tmp_path, True, now=NOW)
    append_prompt_record(tmp_path, "convert_autumn.md", "frame3", "aaaa.md", now=NOW)
    append_prompt_record(tmp_path, "convert_winter.md", "frame0", "bbbb.md", now=NOW)
    data = read(tmp_path)
    assert data["approved"] is True
    assert data["prompts"] == [
        {
            "prompt": "convert_autumn.md",
            "frame": "frame3",
            "queued_at": timestamp(NOW),
            "queue_file": "aaaa.md",
        },
        {
            "prompt": "convert_winter.md",
            "frame": "frame0",
            "queued_at": timestamp(NOW),
            "queue_file": "bbbb.md",
        },
    ]


def test_write_into_a_missing_folder_raises(tmp_path):
    with pytest.raises(OSError):
        write_approved(tmp_path / "missing", True)


def test_delete_folder_removes_everything_also_read_only_files(tmp_path):
    folder = tmp_path / "anim"
    (folder / "frame0").mkdir(parents=True)
    locked = folder / "frame0" / "render.png"
    locked.write_bytes(b"x")
    os.chmod(locked, stat.S_IREAD)
    delete_folder(folder)
    assert not folder.exists()


def test_delete_missing_folder_raises(tmp_path):
    with pytest.raises(OSError):
        delete_folder(tmp_path / "missing")
