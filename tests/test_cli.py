import json
from pathlib import Path

import pytest
import typer
from PIL import Image
from typer.testing import CliRunner

from photobook import __version__
from photobook.cli import _load_manual_order, app

runner = CliRunner()


def _write_photos_json(tmp_path: Path) -> Path:
    image_path = tmp_path / "a.jpg"
    Image.new("RGB", (800, 600), (10, 20, 30)).save(image_path)
    photos_json = tmp_path / "photos.json"
    photos_json.write_text(
        json.dumps(
            [
                {
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
            ]
        ),
        encoding="utf-8",
    )
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
    assert "--review-file and --manual-order" in result.output
