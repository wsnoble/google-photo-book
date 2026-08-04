from __future__ import annotations

from pathlib import Path

from photobook.layout import build_pages
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


def _names(pages) -> list[list[str]]:
    return [[slot.photo.image_path.name for slot in page.slots] for page in pages]


def test_landscape_photos_get_one_per_page() -> None:
    photos = [_make_photo("a.jpg", 800, 600), _make_photo("b.jpg", 800, 600)]
    pages = build_pages(photos)
    assert _names(pages) == [["a.jpg"], ["b.jpg"]]


def test_consecutive_portraits_are_paired() -> None:
    photos = [_make_photo("a.jpg", 600, 800), _make_photo("b.jpg", 600, 800)]
    pages = build_pages(photos)
    assert _names(pages) == [["a.jpg", "b.jpg"]]


def test_odd_portrait_out_gets_its_own_page() -> None:
    photos = [
        _make_photo("a.jpg", 600, 800),
        _make_photo("b.jpg", 800, 600),
    ]
    pages = build_pages(photos)
    assert _names(pages) == [["a.jpg"], ["b.jpg"]]


def test_landscape_between_portraits_flushes_the_pending_one() -> None:
    photos = [
        _make_photo("p1.jpg", 600, 800),
        _make_photo("land.jpg", 800, 600),
        _make_photo("p2.jpg", 600, 800),
        _make_photo("p3.jpg", 600, 800),
    ]
    pages = build_pages(photos)
    assert _names(pages) == [["p1.jpg"], ["land.jpg"], ["p2.jpg", "p3.jpg"]]


def test_panorama_and_square_each_get_their_own_page() -> None:
    photos = [
        _make_photo("pano.jpg", 2400, 800),
        _make_photo("sq.jpg", 800, 800),
    ]
    pages = build_pages(photos)
    assert _names(pages) == [["pano.jpg"], ["sq.jpg"]]


def test_empty_photo_list_produces_no_pages() -> None:
    assert build_pages([]) == []
