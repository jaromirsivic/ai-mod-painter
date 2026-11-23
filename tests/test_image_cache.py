from __future__ import annotations

from PySide6.QtCore import QSize

from ai_mod_painter.core.image_cache import ImageCache
from tests.conftest import make_image


def test_lru_eviction_by_bytes(qapp, tmp_path):
    paths = [make_image(tmp_path / f"{i}.png", size=(10, 10)) for i in range(4)]
    one = 10 * 10 * 4
    cache = ImageCache(cap_bytes=one * 2)
    cache.load_now(paths[0])
    cache.load_now(paths[1])
    cache.get(paths[0])  # touch: 1 is now the least recently used
    cache.load_now(paths[2])
    assert paths[0] in cache and paths[2] in cache
    assert paths[1] not in cache
    assert cache.used_bytes == one * 2


def test_size_of_without_decoding(qapp, tmp_path):
    path = make_image(tmp_path / "a.png", size=(7, 3))
    cache = ImageCache()
    assert cache.size_of(path) == QSize(7, 3)
    assert path not in cache
    assert not cache.size_of(tmp_path / "missing.png").isValid()


def test_background_request_loads_and_signals(qtbot, tmp_path):
    paths = [make_image(tmp_path / f"{i}.png") for i in range(6)]
    cache = ImageCache(workers=2)
    loaded = []
    cache.image_loaded.connect(loaded.append)
    cache.request(paths + [paths[0]])
    qtbot.waitUntil(lambda: len(loaded) == 6, timeout=5000)
    assert set(loaded) == set(paths)
    assert all(cache.is_ready(p) for p in paths)
    cache.shutdown()


def test_request_replaces_the_queue(qtbot, tmp_path):
    paths = [make_image(tmp_path / f"{i}.png") for i in range(8)]
    cache = ImageCache(workers=1)
    loaded = []
    cache.image_loaded.connect(loaded.append)
    cache.request(paths[:4])  # the first one starts decoding at once
    cache.request(paths[6:])  # the rest of the old queue is dropped
    qtbot.waitUntil(lambda: len(loaded) == 3, timeout=5000)
    qtbot.wait(100)
    assert set(loaded) == {paths[0], paths[6], paths[7]}
    cache.shutdown()
