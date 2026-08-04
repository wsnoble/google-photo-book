from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from photobook.model import Photo
from photobook.render import build_book_pdf


def _make_photo(tmp_path: Path, name: str, width: int, height: int, **overrides) -> Photo:
    image_path = tmp_path / name
    Image.new("RGB", (width, height), (10, 20, 30)).save(image_path)

    defaults: dict = {
        "image_path": image_path,
        "metadata_path": None,
        "timestamp": None,
        "timestamp_source": "unknown",
        "caption": None,
        "google_photos_url": None,
        "width": width,
        "height": height,
        "orientation": 1,
        "edited": False,
        "warnings": [],
    }
    defaults.update(overrides)
    return Photo(**defaults)


def _landscape(tmp_path: Path, name: str, **overrides) -> Photo:
    return _make_photo(tmp_path, name, 800, 600, **overrides)


def test_build_book_pdf_page_count_matches_layout_pattern(tmp_path: Path) -> None:
    # Pattern is 5, 4, 5, 4, 2 -> 9 photos makes one 5-photo page and one
    # 4-photo page.
    photos = [_landscape(tmp_path, f"p{i}.jpg") for i in range(9)]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    assert output.is_file()
    reader = PdfReader(str(output))
    assert len(reader.pages) == 2


def test_panorama_gets_its_own_page(tmp_path: Path) -> None:
    photos = [
        _landscape(tmp_path, "a.jpg"),
        _make_photo(tmp_path, "wide.jpg", 2400, 800),
        _landscape(tmp_path, "b.jpg"),
    ]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    # The pending 1-photo batch is flushed before the panorama's solo page,
    # then the remaining photo starts a fresh batch: 3 pages total.
    assert len(PdfReader(str(output)).pages) == 3


def test_book_pdf_page_size_is_10x8in_landscape(tmp_path: Path) -> None:
    photos = [_landscape(tmp_path, "a.jpg")]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    page = PdfReader(str(output)).pages[0]
    # 1in = 72pt.
    assert round(float(page.mediabox.width)) == 720
    assert round(float(page.mediabox.height)) == 576


def test_caption_present_and_absent(tmp_path: Path) -> None:
    photos = [
        _landscape(tmp_path, "captioned.jpg", caption="A lovely view"),
        _landscape(tmp_path, "plain.jpg", caption=None),
    ]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    text = "".join(page.extract_text() for page in PdfReader(str(output)).pages)
    assert "A lovely view" in text


def test_caption_with_markup_is_escaped_not_interpreted(tmp_path: Path) -> None:
    # Regression test: template filenames ending in ".html.jinja" don't
    # match select_autoescape's ".html" suffix check, which silently
    # disabled autoescaping. If a caption's "<b>" were interpreted as a
    # real tag instead of escaped text, it would vanish from extracted
    # text (consumed as markup) rather than appearing literally.
    photos = [_landscape(tmp_path, "a.jpg", caption="<b>bold</b> caption")]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    text = "".join(page.extract_text() for page in PdfReader(str(output)).pages)
    assert "<b>bold</b> caption" in text
