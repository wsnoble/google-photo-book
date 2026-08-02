from __future__ import annotations

import csv
import json
from pathlib import Path

from photobook.importer import scan_album
from photobook.validation import summarize, write_photos_json, write_report_csv, write_report_txt


def test_summarize_counts_match_fixture(sample_takeout: Path) -> None:
    result = scan_album(sample_takeout)

    assert summarize(result) == {
        "printable_images": 5,
        "videos_skipped": 1,
        "captions_found": 4,
        "captions_missing": 1,
        "metadata_inherited": 1,
        "unmatched_images": 1,
        "unused_json_files": 1,
    }


def test_write_photos_json_round_trips_all_photos(sample_takeout: Path, tmp_path: Path) -> None:
    result = scan_album(sample_takeout)
    out = tmp_path / "photos.json"

    write_photos_json(result, out)
    data = json.loads(out.read_text(encoding="utf-8"))

    assert len(data) == len(result.photos)
    assert {"image_path", "caption", "timestamp", "edited", "warnings"} <= data[0].keys()


def test_write_report_csv_has_one_row_per_photo(sample_takeout: Path, tmp_path: Path) -> None:
    result = scan_album(sample_takeout)
    out = tmp_path / "report.csv"

    write_report_csv(result, out)
    with out.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))

    assert rows[0] == [
        "image_path",
        "timestamp",
        "timestamp_source",
        "caption",
        "edited",
        "warnings",
    ]
    assert len(rows) - 1 == len(result.photos)


def test_write_report_txt_lists_unmatched_and_unused_files(
    sample_takeout: Path, tmp_path: Path
) -> None:
    result = scan_album(sample_takeout)
    out = tmp_path / "report.txt"

    write_report_txt(result, out)
    text = out.read_text(encoding="utf-8")

    assert "printable_images: 5" in text
    assert "IMG_0004.jpg" in text
    assert "IMG_0005.jpg.supplemental-metadata.json" in text
