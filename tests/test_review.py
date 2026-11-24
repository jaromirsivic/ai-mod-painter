from __future__ import annotations

import json
import os
import stat

import pytest

from ai_mod_painter.core.review import CONFIG_NAME, delete_folder, read_approved, write_approved


def test_missing_or_broken_config_is_not_approved(tmp_path):
    assert not read_approved(tmp_path)
    (tmp_path / CONFIG_NAME).write_text("{not json", encoding="utf-8")
    assert not read_approved(tmp_path)
    (tmp_path / CONFIG_NAME).write_text("[true]", encoding="utf-8")
    assert not read_approved(tmp_path)
    (tmp_path / CONFIG_NAME).write_text('{"approved": "yes"}', encoding="utf-8")
    assert not read_approved(tmp_path)


def test_write_and_read_back_keeping_other_keys(tmp_path):
    (tmp_path / CONFIG_NAME).write_text('{"note": "keep me"}', encoding="utf-8")
    write_approved(tmp_path, True)
    assert read_approved(tmp_path)
    data = json.loads((tmp_path / CONFIG_NAME).read_text(encoding="utf-8"))
    assert data == {"note": "keep me", "approved": True}

    write_approved(tmp_path, False)
    assert not read_approved(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [CONFIG_NAME]  # no temp file left


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
