from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

from photobook.imaging import MAX_LONG_EDGE_PX, prepare_for_print


def test_large_image_is_downsampled_to_the_cap(tmp_path: Path) -> None:
    source = tmp_path / "big.jpg"
    Image.new("RGB", (5000, 3000), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    result = prepare_for_print(source, cache_dir)

    with Image.open(result) as img:
        assert max(img.size) <= MAX_LONG_EDGE_PX
        # aspect ratio preserved (5000:3000 == 5:3)
        assert abs(img.size[0] / img.size[1] - 5000 / 3000) < 0.01


def test_small_image_is_not_upsampled(tmp_path: Path) -> None:
    source = tmp_path / "small.jpg"
    Image.new("RGB", (400, 300), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    result = prepare_for_print(source, cache_dir)

    with Image.open(result) as img:
        assert img.size == (400, 300)


def test_result_is_cached_on_second_call(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (3000, 2000), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    first = prepare_for_print(source, cache_dir)
    first_mtime = first.stat().st_mtime_ns
    second = prepare_for_print(source, cache_dir)

    assert first == second
    assert second.stat().st_mtime_ns == first_mtime  # not rewritten


def test_cache_key_changes_when_source_changes(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (3000, 2000), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    first = prepare_for_print(source, cache_dir)

    # Overwrite with different content and a forced, distinct mtime (some
    # filesystems have coarse mtime resolution, so don't rely on the save
    # alone to bump it).
    Image.new("RGB", (3000, 2000), (200, 200, 200)).save(source)
    later = source.stat().st_mtime + 5
    os.utime(source, (later, later))
    second = prepare_for_print(source, cache_dir)

    assert first != second
