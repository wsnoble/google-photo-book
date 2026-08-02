from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from photobook.model import Photo
from photobook.proof import build_proof_pdf


def _make_photo(tmp_path: Path, name: str, **overrides) -> Photo:
    image_path = tmp_path / name
    Image.new("RGB", (200, 150), (10, 20, 30)).save(image_path)

    defaults: dict = {
        "image_path": image_path,
        "metadata_path": None,
        "timestamp": datetime(2020, 1, 1, tzinfo=UTC),
        "timestamp_source": "photoTakenTime",
        "caption": None,
        "google_photos_url": None,
        "width": 200,
        "height": 150,
        "orientation": 1,
        "edited": False,
        "warnings": [],
    }
    defaults.update(overrides)
    return Photo(**defaults)


def test_build_proof_pdf_produces_one_page_per_few_photos(tmp_path: Path) -> None:
    photos = [
        _make_photo(tmp_path, "a.jpg", caption="Caption A"),
        _make_photo(tmp_path, "b.jpg", caption="Caption B"),
    ]
    output = tmp_path / "proof.pdf"

    build_proof_pdf(photos, output)

    assert output.is_file()
    reader = PdfReader(str(output))
    assert len(reader.pages) >= 1


def test_proof_pdf_text_includes_filenames_captions_and_order(tmp_path: Path) -> None:
    photos = [
        _make_photo(
            tmp_path,
            "second.jpg",
            timestamp=datetime(2020, 6, 1, tzinfo=UTC),
            caption="Second caption",
        ),
        _make_photo(
            tmp_path,
            "first.jpg",
            timestamp=datetime(2020, 1, 1, tzinfo=UTC),
            caption="First caption",
        ),
    ]
    output = tmp_path / "proof.pdf"

    build_proof_pdf(photos, output)

    text = "".join(page.extract_text() for page in PdfReader(str(output)).pages)
    assert "first.jpg" in text
    assert "First caption" in text
    assert "second.jpg" in text
    assert "Second caption" in text
    # Ordered by timestamp, so "first.jpg" (Jan) must appear before "second.jpg" (Jun).
    assert text.index("first.jpg") < text.index("second.jpg")


def test_proof_pdf_flags_missing_caption_and_warnings(tmp_path: Path) -> None:
    photos = [
        _make_photo(
            tmp_path,
            "no_caption.jpg",
            caption=None,
            timestamp=None,
            timestamp_source="unknown",
            warnings=["no caption", "timestamp unknown"],
        ),
    ]
    output = tmp_path / "proof.pdf"

    build_proof_pdf(photos, output)

    text = "".join(page.extract_text() for page in PdfReader(str(output)).pages)
    assert "no caption" in text.lower()
    assert "timestamp unknown" in text.lower()
    assert "Unknown date" in text
