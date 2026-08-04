from __future__ import annotations

from pathlib import Path

from photobook.layout import _split_into_rows, build_pages
from photobook.model import Photo


def _make_photo(name: str, width: int, height: int) -> Photo:
    return Photo(
        image_path=Path(f"/album/{name}"),
        metadata_path=None,
        timestamp=None,
        timestamp_source="unknown",
        caption=None,
        google_photos_url=None,
        width=width,
        height=height,
        orientation=1,
        edited=False,
    )


def _landscape(name: str) -> Photo:
    return _make_photo(name, 800, 600)


def _panorama(name: str) -> Photo:
    return _make_photo(name, 2400, 800)


def _names_per_page(pages) -> list[list[str]]:
    return [[slot.photo.image_path.name for slot in page.slots] for page in pages]


def test_split_into_rows_five_is_three_and_two() -> None:
    assert _split_into_rows(5) == [3, 2]


def test_split_into_rows_four_is_two_and_two() -> None:
    assert _split_into_rows(4) == [2, 2]


def test_split_into_rows_two_or_fewer_is_a_single_row() -> None:
    assert _split_into_rows(2) == [2]
    assert _split_into_rows(1) == [1]
    assert _split_into_rows(0) == []


def test_pages_follow_the_size_pattern_5_4_5_4_2() -> None:
    photos = [_landscape(f"p{i}.jpg") for i in range(20)]
    pages = build_pages(photos)
    assert [len(page.slots) for page in pages] == [5, 4, 5, 4, 2]


def test_pattern_repeats_and_a_short_remainder_forms_its_own_page() -> None:
    photos = [_landscape(f"p{i}.jpg") for i in range(23)]
    pages = build_pages(photos)
    # 5 + 4 + 5 + 4 + 2 = 20, then the pattern restarts: 3 left over.
    assert [len(page.slots) for page in pages] == [5, 4, 5, 4, 2, 3]


def test_panorama_gets_its_own_page_without_disrupting_the_pattern() -> None:
    photos = [_landscape("a.jpg"), _panorama("wide.jpg"), _landscape("b.jpg"), _landscape("c.jpg")]
    pages = build_pages(photos)
    # The pending 1-photo batch is flushed before the panorama's solo page,
    # and the pattern's first slot (size 5) isn't consumed by either.
    assert _names_per_page(pages) == [["a.jpg"], ["wide.jpg"], ["b.jpg", "c.jpg"]]
    assert len(pages[1].slots) == 1
    assert pages[1].slots[0].orientation == "panorama"


def test_solo_page_has_a_single_row() -> None:
    pages = build_pages([_panorama("wide.jpg")])
    assert pages[0].rows == [1]


def test_empty_photo_list_produces_no_pages() -> None:
    assert build_pages([]) == []
