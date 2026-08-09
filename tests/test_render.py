from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from photobook.layout import Page, PageSlot
from photobook.model import Photo
from photobook.render import (
    _SAFE_AREA_LEFT_RIGHT_PT,
    _SAFE_AREA_TOP_BOTTOM_PT,
    PAGE_HEIGHT_PT,
    PAGE_WIDTH_PT,
    _page_to_template_data,
    build_book_pdf,
)


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


def test_book_pdf_page_size_matches_blurb_spec(tmp_path: Path) -> None:
    # Verified 2026-08-06 against Blurb's Specification Calculator for
    # Standard Landscape, Hardcover ImageWrap, Standard paper: exported
    # page PDF is 693x594pt (trim 684x576pt + bleed). Not 720x576pt
    # (10x8in) -- the real trim is 9.5x8in despite the "10x8" name.
    photos = [_landscape(tmp_path, "a.jpg")]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    page = PdfReader(str(output)).pages[0]
    assert round(float(page.mediabox.width)) == 693
    assert round(float(page.mediabox.height)) == 594


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


def test_page_to_template_data_rejects_rows_that_dont_match_slot_count(tmp_path: Path) -> None:
    photo = _landscape(tmp_path, "a.jpg")
    # rows sums to 3, but there's only 1 slot -- would otherwise silently
    # produce empty/wrong rows instead of failing loudly.
    mismatched_page = Page(slots=[PageSlot(photo=photo, orientation="landscape")], rows=[3])

    with pytest.raises(ValueError, match="doesn't match"):
        _page_to_template_data(mismatched_page, tmp_path / "cache")


def test_safe_area_matches_the_blurb_spec_constants() -> None:
    # Exact, not a loose bound: these are fixed constants pulled from
    # Blurb's spec, so a wrong value (e.g. a typo) should fail this test
    # rather than slide under a generous ">" threshold.
    content_width = PAGE_WIDTH_PT - 2 * _SAFE_AREA_LEFT_RIGHT_PT
    content_height = PAGE_HEIGHT_PT - 2 * _SAFE_AREA_TOP_BOTTOM_PT
    assert content_width == 603
    assert content_height == 540


_ROME = (41.9028, 12.4964)
_PARIS = (48.8566, 2.3522)


def test_chapters_true_inserts_divider_pages_titled_by_country(tmp_path: Path) -> None:
    photos = [
        _landscape(tmp_path, "rome.jpg", latitude=_ROME[0], longitude=_ROME[1]),
        _landscape(tmp_path, "paris.jpg", latitude=_PARIS[0], longitude=_PARIS[1]),
    ]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output, chapters=True)

    pages = PdfReader(str(output)).pages
    # Each country only has 1 photo (fewer than the divider page's 3-photo
    # capacity), so it's absorbed directly onto the divider page itself
    # rather than spilling onto a separate page.
    assert len(pages) == 2
    assert "Italy" in pages[0].extract_text()
    assert "France" in pages[1].extract_text()


def test_chapter_divider_holds_up_to_three_photos_the_rest_spill_over(tmp_path: Path) -> None:
    photos = [
        _landscape(tmp_path, f"rome{i}.jpg", latitude=_ROME[0], longitude=_ROME[1])
        for i in range(5)
    ]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output, chapters=True)

    pages = PdfReader(str(output)).pages
    # Divider page takes the first 3; the remaining 2 land on their own
    # ordinary grid page.
    assert len(pages) == 2
    assert "Italy" in pages[0].extract_text()


def test_chapter_divider_skips_a_force_solo_true_photo(tmp_path: Path) -> None:
    forced = _landscape(
        tmp_path, "forced.jpg", latitude=_ROME[0], longitude=_ROME[1], force_solo=True
    )
    photos = [forced] + [
        _landscape(tmp_path, f"rome{i}.jpg", latitude=_ROME[0], longitude=_ROME[1])
        for i in range(3)
    ]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output, chapters=True)

    pages = PdfReader(str(output)).pages
    # The divider absorbs the 3 non-forced photos (skipping "forced.jpg",
    # which wants a full page to itself even though it would otherwise be
    # divider-eligible by position), then "forced.jpg" gets its own page.
    assert len(pages) == 2
    assert "Italy" in pages[0].extract_text()


def test_chapters_false_default_has_no_dividers(tmp_path: Path) -> None:
    photos = [
        _landscape(tmp_path, "rome.jpg", latitude=_ROME[0], longitude=_ROME[1]),
        _landscape(tmp_path, "paris.jpg", latitude=_PARIS[0], longitude=_PARIS[1]),
    ]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output)

    # No chapters requested -> both photos land on one ordinary 2-photo grid
    # page, no divider inserted despite differing countries.
    assert len(PdfReader(str(output)).pages) == 1


def test_review_file_controls_order_chapters_and_captions(tmp_path: Path) -> None:
    a = _landscape(tmp_path, "a.jpg")
    b = _landscape(tmp_path, "b.jpg")
    c = _landscape(tmp_path, "c.jpg")  # omitted from the review file entirely
    tsv = tmp_path / "review.tsv"
    tsv.write_text(
        "row_type\timage_path\tfilename\tdate\ttag\tchapter_title\n"
        "chapter\t\t\t\t\tFrance\n"
        f"photo\t{b.image_path}\tb.jpg\t\tA real caption\t\n"
        f"photo\t{a.image_path}\ta.jpg\t\t(auto description)\t\n",
        encoding="utf-8",
    )
    output = tmp_path / "book.pdf"

    build_book_pdf([a, b, c], output, review_file=tsv)

    reader = PdfReader(str(output))
    # Only 2 photos in the France group (fewer than the divider page's
    # 3-photo capacity), so both land directly on the divider page itself,
    # in the file's order (b before a) -- `c` was never listed, so it must
    # not appear at all.
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "France" in text
    assert "A real caption" in text
    assert "auto description" not in text


def test_chapters_true_does_not_repeat_divider_across_a_none_labeled_gap(tmp_path: Path) -> None:
    # rome, rome, an undated/GPS-less photo (no timestamp or GPS -> country
    # None, can't be assigned to either chapter), then rome again. Must
    # render exactly one "Italy" divider, not two.
    photos = [
        _landscape(tmp_path, "rome1.jpg", latitude=_ROME[0], longitude=_ROME[1]),
        _landscape(tmp_path, "rome2.jpg", latitude=_ROME[0], longitude=_ROME[1]),
        _landscape(tmp_path, "mystery.jpg"),
        _landscape(tmp_path, "rome3.jpg", latitude=_ROME[0], longitude=_ROME[1]),
    ]
    output = tmp_path / "book.pdf"

    build_book_pdf(photos, output, chapters=True)

    text = "".join(page.extract_text() for page in PdfReader(str(output)).pages)
    assert text.count("Italy") == 1
