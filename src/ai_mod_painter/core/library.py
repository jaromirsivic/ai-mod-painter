"""The folder model: root -> animation folders -> frame folders -> images.

The rules are universal and never look at particular names:

- an animation is every direct subfolder of the root;
- a frame is every direct subfolder of an animation that holds at least one image
  (frame folders without images are skipped);
- an image is a file with an extension from ``IMAGE_EXTENSIONS`` (case-insensitive);
  every other file is ignored;
- a layer is an image file name, compared case-insensitively, and is the union over all
  frames of the animation.

Folders and frames are sorted naturally (``frame2`` before ``frame10``).
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})
PAGE_SIZE = 100

_DIGITS = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple:
    """Sort key that orders embedded numbers by value: ``a2`` < ``a10``.

    Text parts sit at even positions and numbers at odd positions, so keys of different
    names always compare element by element with matching types. The original name is
    the last element, so the order is total and stable.
    """
    parts = _DIGITS.split(name.casefold())
    return (
        tuple(int(part) if i % 2 else part for i, part in enumerate(parts)),
        name,
    )


def layer_key(file_name: str) -> str:
    return file_name.casefold()


@dataclass(frozen=True)
class Frame:
    name: str
    path: Path
    files: dict[str, Path]
    """Layer key -> image file of this frame."""


@dataclass(frozen=True)
class Layer:
    key: str
    name: str
    """The file name as first seen (original letter case)."""
    frame_count: int


@dataclass(frozen=True)
class Animation:
    path: Path
    frames: list[Frame]
    layers: list[Layer] = field(default_factory=list)
    """Default order, bottom first: most frequent layer at the bottom, ties by name."""

    @property
    def name(self) -> str:
        return self.path.name


def _subfolders(folder: Path) -> list[os.DirEntry]:
    with os.scandir(folder) as entries:
        return [e for e in entries if _is_dir(e)]


def _is_dir(entry: os.DirEntry) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        return False


def _is_file(entry: os.DirEntry) -> bool:
    try:
        return entry.is_file()
    except OSError:
        return False


def list_animations(root: Path) -> list[Path]:
    """Every direct subfolder of ``root``, sorted naturally ascending.

    Raises ``OSError`` (``FileNotFoundError``, ``NotADirectoryError``,
    ``PermissionError``) when the root cannot be listed.
    """
    root = Path(root)
    folders = _subfolders(root)
    folders.sort(key=lambda e: natural_key(e.name))
    return [Path(e.path) for e in folders]


def page_count(total: int, size: int = PAGE_SIZE) -> int:
    return max(1, math.ceil(total / size))


def page(items: Sequence, index: int, size: int = PAGE_SIZE) -> list:
    """Items of page ``index`` (0-based); the index is clamped to the valid pages."""
    index = min(max(index, 0), page_count(len(items), size) - 1)
    return list(items[index * size : (index + 1) * size])


def _frame_images(folder: Path) -> list[tuple[str, Path]]:
    with os.scandir(folder) as entries:
        images = [
            (e.name, Path(e.path))
            for e in entries
            if os.path.splitext(e.name)[1].casefold() in IMAGE_EXTENSIONS and _is_file(e)
        ]
    images.sort(key=lambda item: natural_key(item[0]))
    return images


def scan_animation(folder: Path) -> Animation:
    """Frames (with images) and layers of one animation folder.

    Raises ``OSError`` when the animation folder itself cannot be listed; frame folders
    that cannot be read are skipped.
    """
    folder = Path(folder)
    subfolders = _subfolders(folder)
    subfolders.sort(key=lambda e: natural_key(e.name))

    frames: list[Frame] = []
    names: dict[str, str] = {}
    counts: dict[str, int] = {}
    for entry in subfolders:
        try:
            images = _frame_images(Path(entry.path))
        except OSError:
            continue
        if not images:
            continue
        files: dict[str, Path] = {}
        for file_name, path in images:
            key = layer_key(file_name)
            if key in files:  # same name in another letter case: keep the first
                continue
            files[key] = path
            names.setdefault(key, file_name)
            counts[key] = counts.get(key, 0) + 1
        frames.append(Frame(name=entry.name, path=Path(entry.path), files=files))

    layers = [Layer(key=key, name=names[key], frame_count=counts[key]) for key in names]
    layers.sort(key=lambda layer: (-layer.frame_count, natural_key(layer.name)))
    return Animation(path=folder, frames=frames, layers=layers)
