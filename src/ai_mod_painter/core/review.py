"""Review of animation folders: the review log file and permanent deletion.

The log lives in ``ai-mod-config.json`` directly in the animation folder (next to its
frame folders). The library ignores it, as it ignores every file of an animation
folder. The file holds a JSON object; keys the app does not know are kept when it is
rewritten::

    {
      "approved": true,
      "approved_changed_at": "2026-11-24T06:35:12+01:00",
      "prompts": [
        {"prompt": "convert_autumn.md", "frame": "frame3",
         "queued_at": "2026-11-24T06:36:40+01:00", "queue_file": "3f9a0c1d2e4b5a67.md"}
      ]
    }

Times are local ISO 8601 with the UTC offset, to the second.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from datetime import datetime
from pathlib import Path

CONFIG_NAME = "ai-mod-config.json"
APPROVED_KEY = "approved"
APPROVED_CHANGED_KEY = "approved_changed_at"
PROMPTS_KEY = "prompts"


def timestamp(now: datetime | None = None) -> str:
    """Local time with the UTC offset, to the second: ``2026-11-24T06:35:12+01:00``."""
    return (now or datetime.now()).astimezone().isoformat(timespec="seconds")


def _read_config(folder: Path) -> dict:
    try:
        data = json.loads((Path(folder) / CONFIG_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_config(folder: Path, config: dict) -> None:
    folder = Path(folder)
    temp = folder / f".{CONFIG_NAME}.tmp"
    temp.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, folder / CONFIG_NAME)


def read_approved(folder: Path) -> bool:
    """``True`` only when the config file exists and says ``"approved": true``."""
    return _read_config(folder).get(APPROVED_KEY) is True


def write_approved(folder: Path, approved: bool, now: datetime | None = None) -> None:
    """Store the approval and the time of the change, atomically.

    Raises ``OSError`` when it cannot be written.
    """
    config = _read_config(folder)
    config[APPROVED_KEY] = approved
    config[APPROVED_CHANGED_KEY] = timestamp(now)
    _write_config(folder, config)


def append_prompt_record(
    folder: Path,
    prompt: str,
    frame: str,
    queue_file: str,
    now: datetime | None = None,
) -> None:
    """Add one entry to ``prompts`` (a history: every Add adds one).

    Raises ``OSError`` when it cannot be written.
    """
    config = _read_config(folder)
    records = config.get(PROMPTS_KEY)
    if not isinstance(records, list):
        records = []
    records.append(
        {"prompt": prompt, "frame": frame, "queued_at": timestamp(now), "queue_file": queue_file}
    )
    config[PROMPTS_KEY] = records
    _write_config(folder, config)


def _retry_writable(function, path, error: BaseException) -> None:
    """``shutil.rmtree`` error handler: clear the read-only flag and try once more."""
    if not isinstance(error, PermissionError):
        raise error
    os.chmod(path, stat.S_IWRITE)
    function(path)


def delete_folder(folder: Path) -> None:
    """Delete the folder with everything in it, permanently (no Recycle Bin).

    Raises ``OSError`` when it cannot be deleted completely.
    """
    shutil.rmtree(Path(folder), onexc=_retry_writable)
