from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from photobook.cover import (
    COVER_PAGE_HEIGHT_PT,
    COVER_PAGE_WIDTH_PT,
    COVER_VERIFIED_PAGE_COUNT,
    build_cover_pdf,
)
from photobook.model import Photo


def _make_photo(tmp_path: Path, name: str, width: int, height: int) -> Photo:
    image_path = tmp_path / name
    Image.new("RGB", (width, height), (10, 20, 30)).save(image_path)
    return Photo(
        image_path=image_path,
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


def test_wrong_page_count_is_rejected(tmp_path: Path) -> None:
    front = _make_photo(tmp_path, "front.jpg", 3000, 2000)
    back = _make_photo(tmp_path, "back.jpg", 3000, 2000)
    output = tmp_path / "cover.pdf"

    with pytest.raises(ValueError, match="90"):
        build_cover_pdf(
            front,
            back,
            output,
            interior_page_count=COVER_VERIFIED_PAGE_COUNT + 2,
            book_title="Our Trip",
        )

    assert not output.is_file()


def test_builds_a_single_page_cover_at_the_blurb_spec_size(tmp_path: Path) -> None:
    front = _make_photo(tmp_path, "front.jpg", 3000, 2000)
    back = _make_photo(tmp_path, "back.jpg", 3000, 2000)
    output = tmp_path / "cover.pdf"

    build_cover_pdf(
        front,
        back,
        output,
        interior_page_count=COVER_VERIFIED_PAGE_COUNT,
        book_title="Our Trip",
        book_subtitle="Summer 2026",
    )

    assert output.is_file()
    pages = PdfReader(str(output)).pages
    assert len(pages) == 1
    assert float(pages[0].mediabox.width) == pytest.approx(COVER_PAGE_WIDTH_PT, abs=0.1)
    assert float(pages[0].mediabox.height) == pytest.approx(COVER_PAGE_HEIGHT_PT, abs=0.1)
    text = pages[0].extract_text()
    assert "Our Trip" in text
    assert "Summer 2026" in text


def test_title_appears_without_a_subtitle(tmp_path: Path) -> None:
    front = _make_photo(tmp_path, "front.jpg", 3000, 2000)
    back = _make_photo(tmp_path, "back.jpg", 3000, 2000)
    output = tmp_path / "cover.pdf"

    build_cover_pdf(
        front, back, output, interior_page_count=COVER_VERIFIED_PAGE_COUNT, book_title="Our Trip"
    )

    text = PdfReader(str(output)).pages[0].extract_text()
    assert "Our Trip" in text


def test_title_with_a_manual_line_break_still_builds_a_valid_pdf(tmp_path: Path) -> None:
    front = _make_photo(tmp_path, "front.jpg", 3000, 2000)
    back = _make_photo(tmp_path, "back.jpg", 3000, 2000)
    output = tmp_path / "cover.pdf"

    build_cover_pdf(
        front,
        back,
        output,
        interior_page_count=COVER_VERIFIED_PAGE_COUNT,
        book_title="Our Trip and\nthe Sequel",
    )

    text = PdfReader(str(output)).pages[0].extract_text()
    assert "Our Trip and" in text
    assert "the Sequel" in text
