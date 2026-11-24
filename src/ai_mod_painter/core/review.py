"""Review of animation folders: the approval file and permanent deletion.

The approval lives in ``ai-mod-config.json`` directly in the animation folder (next to
its frame folders). The library ignores it, as it ignores every file of an animation
folder. The file holds a JSON object; keys other than ``approved`` are kept when it is
rewritten.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

CONFIG_NAME = "ai-mod-config.json"
APPROVED_KEY = "approved"


def _read_config(folder: Path) -> dict:
    try:
        data = json.loads((Path(folder) / CONFIG_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_approved(folder: Path) -> bool:
    """``True`` only when the config file exists and says ``"approved": true``."""
    return _read_config(folder).get(APPROVED_KEY) is True


def write_approved(folder: Path, approved: bool) -> None:
    """Store the approval atomically. Raises ``OSError`` when it cannot be written."""
    folder = Path(folder)
    config = _read_config(folder)
    config[APPROVED_KEY] = approved
    target = folder / CONFIG_NAME
    temp = folder / f".{CONFIG_NAME}.tmp"
    temp.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, target)


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
