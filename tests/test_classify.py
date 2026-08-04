from __future__ import annotations

from pathlib import Path

from photobook.classify import classify_photo
from photobook.model import Photo


def _make_photo(width: int, height: int, orientation: int = 1) -> Photo:
    return Photo(
        image_path=Path("/album/photo.jpg"),
        metadata_path=None,
        timestamp=None,
        timestamp_source="unknown",
        caption=None,
        google_photos_url=None,
        width=width,
        height=height,
        orientation=orientation,
        edited=False,
    )


def test_classify_landscape() -> None:
    assert classify_photo(_make_photo(800, 600)) == "landscape"


def test_classify_portrait() -> None:
    assert classify_photo(_make_photo(600, 800)) == "portrait"


def test_classify_square() -> None:
    assert classify_photo(_make_photo(800, 800)) == "square"


def test_classify_square_within_tolerance() -> None:
    assert classify_photo(_make_photo(800, 780)) == "square"


def test_classify_wide_panorama() -> None:
    assert classify_photo(_make_photo(2400, 800)) == "panorama"


def test_classify_tall_panorama() -> None:
    assert classify_photo(_make_photo(800, 2400)) == "panorama"


def test_classify_accounts_for_exif_rotation() -> None:
    # Stored as landscape dimensions, but EXIF orientation 6 (90 deg CW)
    # means it actually displays as portrait.
    photo = _make_photo(800, 600, orientation=6)
    assert classify_photo(photo) == "portrait"


def test_classify_zero_dimensions_falls_back_to_landscape() -> None:
    assert classify_photo(_make_photo(0, 0)) == "landscape"
