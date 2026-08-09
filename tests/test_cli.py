import json
import re
from pathlib import Path

import pytest
import typer
from PIL import Image
from pypdf import PdfWriter
from typer.testing import CliRunner

from photobook import __version__
from photobook.cli import _load_manual_order, app

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _plain_text(output: str) -> str:
    """Strip ANSI color codes and collapse whitespace/line-wrapping, since
    Typer's error output wraps and colors differently depending on the
    terminal width/color support it detects -- observed to differ between
    a local run and CI, breaking a plain substring check otherwise."""
    return " ".join(_ANSI_RE.sub("", output).split())


def _photo_dict(image_path: Path) -> dict:
    return {
        "image_path": str(image_path),
        "metadata_path": None,
        "timestamp": None,
        "timestamp_source": "unknown",
        "caption": None,
        "google_photos_url": None,
        "width": 800,
        "height": 600,
        "orientation": 1,
        "edited": False,
        "warnings": [],
    }


def _write_photos_json(tmp_path: Path) -> Path:
    image_path = tmp_path / "a.jpg"
    Image.new("RGB", (800, 600), (10, 20, 30)).save(image_path)
    photos_json = tmp_path / "photos.json"
    photos_json.write_text(json.dumps([_photo_dict(image_path)]), encoding="utf-8")
    return photos_json


def test_version_command_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_load_manual_order_returns_none_when_no_path() -> None:
    assert _load_manual_order(None) is None


def test_load_manual_order_accepts_list_of_strings(tmp_path: Path) -> None:
    path = tmp_path / "order.json"
    path.write_text(json.dumps(["/a.jpg", "/b.jpg"]))

    assert _load_manual_order(path) == ["/a.jpg", "/b.jpg"]


def test_load_manual_order_rejects_non_list(tmp_path: Path) -> None:
    path = tmp_path / "order.json"
    path.write_text(json.dumps({"not": "a list"}))

    with pytest.raises(typer.BadParameter):
        _load_manual_order(path)


def test_load_manual_order_rejects_non_string_items(tmp_path: Path) -> None:
    path = tmp_path / "order.json"
    path.write_text(json.dumps(["/a.jpg", 42]))

    with pytest.raises(typer.BadParameter):
        _load_manual_order(path)


def test_load_manual_order_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "order.json"
    path.write_text("not json{")

    with pytest.raises(typer.BadParameter):
        _load_manual_order(path)


def test_build_rejects_review_file_combined_with_manual_order(tmp_path: Path) -> None:
    photos_json = _write_photos_json(tmp_path)
    manual_order = tmp_path / "order.json"
    manual_order.write_text(json.dumps([]), encoding="utf-8")
    review_file = tmp_path / "review.tsv"
    review_file.write_text("row_type\timage_path\tfilename\tdate\ttag\tchapter_title\n")

    result = runner.invoke(
        app,
        [
            "build",
            str(photos_json),
            "--manual-order",
            str(manual_order),
            "--review-file",
            str(review_file),
        ],
    )

    assert result.exit_code != 0
    assert "--review-file and --manual-order" in _plain_text(result.output)


def test_cover_rejects_an_unknown_front_filename(tmp_path: Path) -> None:
    photos_json = _write_photos_json(tmp_path)
    interior = tmp_path / "interior.pdf"
    interior.write_bytes(b"not a real pdf")

    result = runner.invoke(
        app,
        [
            "cover",
            str(photos_json),
            "--front",
            "does-not-exist.jpg",
            "--back",
            "a.jpg",
            "--interior",
            str(interior),
        ],
    )

    assert result.exit_code != 0
    assert "No photo whose path ends in 'does-not-exist.jpg'" in _plain_text(result.output)


def test_cover_rejects_an_ambiguous_filename(tmp_path: Path) -> None:
    # Two photos sharing a filename in different subfolders -- picking the
    # first match silently would risk putting the wrong image on a
    # physical, unreturnable printed cover.
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    image_a = dir_a / "shared.jpg"
    image_b = dir_b / "shared.jpg"
    Image.new("RGB", (800, 600), (10, 20, 30)).save(image_a)
    Image.new("RGB", (800, 600), (10, 20, 30)).save(image_b)
    photos_json = tmp_path / "photos.json"
    photos_json.write_text(
        json.dumps([_photo_dict(image_a), _photo_dict(image_b)]), encoding="utf-8"
    )
    interior = tmp_path / "interior.pdf"
    interior.write_bytes(b"not a real pdf")

    result = runner.invoke(
        app,
        [
            "cover",
            str(photos_json),
            "--front",
            "shared.jpg",
            "--back",
            "shared.jpg",
            "--interior",
            str(interior),
        ],
    )

    assert result.exit_code != 0
    assert "matches 2 photos" in _plain_text(result.output)


def test_cover_resolves_an_ambiguous_filename_via_a_longer_path(tmp_path: Path) -> None:
    # The ambiguous-match error above tells the user to pass more of the
    # path to disambiguate -- confirm that actually works, rather than
    # being advice the matching logic can't honor.
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    image_a = dir_a / "shared.jpg"
    image_b = dir_b / "shared.jpg"
    Image.new("RGB", (800, 600), (10, 20, 30)).save(image_a)
    Image.new("RGB", (800, 600), (10, 20, 30)).save(image_b)
    photos_json = tmp_path / "photos.json"
    photos_json.write_text(
        json.dumps([_photo_dict(image_a), _photo_dict(image_b)]), encoding="utf-8"
    )
    # A real (if tiny) single-page PDF -- past --front/--back resolution,
    # the command reads its page count, which only a valid PDF supports.
    interior = tmp_path / "interior.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with interior.open("wb") as f:
        writer.write(f)

    result = runner.invoke(
        app,
        [
            "cover",
            str(photos_json),
            "--front",
            "a/shared.jpg",
            "--back",
            "b/shared.jpg",
            "--interior",
            str(interior),
        ],
    )

    # Resolution succeeded (no ambiguity error) -- the command proceeds
    # far enough to hit the unrelated page-count guard instead (raised as
    # a plain ValueError, not a typer.BadParameter, so it surfaces via
    # result.exception rather than result.output), since our 1-page dummy
    # interior isn't the page count the cover was verified for.
    assert "matches 2 photos" not in _plain_text(result.output)
    assert result.exception is not None
    assert "Cover spine width" in str(result.exception)
