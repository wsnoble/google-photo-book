from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

from photobook.imaging import prepare_for_print


def test_cover_fit_downsamples_so_both_dimensions_at_least_fill_the_cell(
    tmp_path: Path,
) -> None:
    # 16:9 photo, worst-case cover crop into a 1256x2250 grid cell (matches
    # the real portrait-cell scenario that motivated placement-aware sizing).
    source = tmp_path / "wide.jpg"
    Image.new("RGB", (5000, 2813), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    result = prepare_for_print(source, cache_dir, 1256, 2250, "cover")

    with Image.open(result) as img:
        assert img.size[0] >= 1256
        assert img.size[1] >= 2250
        # aspect ratio preserved
        assert abs(img.size[0] / img.size[1] - 5000 / 2813) < 0.01


def test_contain_fit_caps_the_long_edge_to_the_larger_cell_dimension(
    tmp_path: Path,
) -> None:
    source = tmp_path / "big.jpg"
    Image.new("RGB", (5000, 3000), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    result = prepare_for_print(source, cache_dir, 2600, 2000, "contain")

    with Image.open(result) as img:
        assert max(img.size) == 2600
        # aspect ratio preserved (5000:3000 == 5:3)
        assert abs(img.size[0] / img.size[1] - 5000 / 3000) < 0.01


def test_small_image_is_not_upsampled(tmp_path: Path) -> None:
    source = tmp_path / "small.jpg"
    Image.new("RGB", (400, 300), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    result = prepare_for_print(source, cache_dir, 2000, 1500, "contain")

    with Image.open(result) as img:
        assert img.size == (400, 300)


def test_small_image_not_upsampled_even_for_cover_fit(tmp_path: Path) -> None:
    source = tmp_path / "small.jpg"
    Image.new("RGB", (400, 300), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    result = prepare_for_print(source, cache_dir, 2000, 1500, "cover")

    with Image.open(result) as img:
        assert img.size == (400, 300)


def test_result_is_cached_on_second_call(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (3000, 2000), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    first = prepare_for_print(source, cache_dir, 1000, 800, "cover")
    first_mtime = first.stat().st_mtime_ns
    second = prepare_for_print(source, cache_dir, 1000, 800, "cover")

    assert first == second
    assert second.stat().st_mtime_ns == first_mtime  # not rewritten


def test_cache_key_changes_when_source_changes(tmp_path: Path) -> None:
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (3000, 2000), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    first = prepare_for_print(source, cache_dir, 1000, 800, "cover")

    # Overwrite with different content and a forced, distinct mtime (some
    # filesystems have coarse mtime resolution, so don't rely on the save
    # alone to bump it).
    Image.new("RGB", (3000, 2000), (200, 200, 200)).save(source)
    later = source.stat().st_mtime + 5
    os.utime(source, (later, later))
    second = prepare_for_print(source, cache_dir, 1000, 800, "cover")

    assert first != second


def test_cache_key_changes_with_placement(tmp_path: Path) -> None:
    # Same source, different cell geometry/fit must not collide in the
    # cache -- each placement needs its own correctly-sized copy.
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (3000, 2000), (10, 20, 30)).save(source)
    cache_dir = tmp_path / "cache"

    cover = prepare_for_print(source, cache_dir, 1000, 800, "cover")
    contain = prepare_for_print(source, cache_dir, 1000, 800, "contain")
    different_size = prepare_for_print(source, cache_dir, 500, 400, "cover")

    assert cover != contain
    assert cover != different_size
