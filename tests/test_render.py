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


def test_build_book_pdf_page_count_matches_layout(tmp_path: Path) -> None:
    photos = [
        _make_photo(tmp_path, "land.jpg", 800, 600),
        _make_photo(tmp_path, "p1.jpg", 600, 800),
        _make_photo(tmp_path, "p2.jpg", 600, 800),
    ]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    assert output.is_file()
    reader = PdfReader(str(output))
    # 1 landscape page + 1 paired-portrait page.
    assert len(reader.pages) == 2


def test_book_pdf_page_size_is_10x8in_landscape(tmp_path: Path) -> None:
    photos = [_make_photo(tmp_path, "land.jpg", 800, 600)]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    page = PdfReader(str(output)).pages[0]
    # 1in = 72pt.
    assert round(float(page.mediabox.width)) == 720
    assert round(float(page.mediabox.height)) == 576


def test_caption_present_and_absent(tmp_path: Path) -> None:
    photos = [
        _make_photo(tmp_path, "captioned.jpg", 800, 600, caption="A lovely view"),
        _make_photo(tmp_path, "plain.jpg", 800, 600, caption=None),
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
    photos = [_make_photo(tmp_path, "a.jpg", 800, 600, caption="<b>bold</b> caption")]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    text = "".join(page.extract_text() for page in PdfReader(str(output)).pages)
    assert "<b>bold</b> caption" in text
