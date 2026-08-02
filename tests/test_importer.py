from __future__ import annotations

from pathlib import Path

from photobook.importer import scan_album


def _by_stem(photos, stem: str):
    return next(p for p in photos if p.image_path.stem == stem)


def test_scan_finds_one_photo_per_logical_image_and_skips_videos(sample_takeout: Path) -> None:
    result = scan_album(sample_takeout)

    stems = sorted(p.image_path.stem for p in result.photos)
    assert stems == ["IMG_0001", "IMG_0002-edited", "IMG_0003", "IMG_0003(1)", "IMG_0004"]
    assert [p.name for p in result.videos_skipped] == ["MVI_0006.mp4"]


def test_prefer_edited_true_selects_edited_variant(sample_takeout: Path) -> None:
    result = scan_album(sample_takeout, prefer_edited=True)

    photo = _by_stem(result.photos, "IMG_0002-edited")
    assert photo.edited is True
    assert photo.caption == "An edited photo"
    assert photo.metadata_path is not None
    assert photo.metadata_path.name == "IMG_0002.jpg.supplemental-metadata.json"


def test_prefer_edited_false_selects_original(sample_takeout: Path) -> None:
    result = scan_album(sample_takeout, prefer_edited=False)

    photo = _by_stem(result.photos, "IMG_0002")
    assert photo.edited is False
    assert photo.caption == "An edited photo"


def test_duplicate_suffixed_files_are_distinct_photos_with_own_metadata(
    sample_takeout: Path,
) -> None:
    result = scan_album(sample_takeout)

    first = _by_stem(result.photos, "IMG_0003")
    second = _by_stem(result.photos, "IMG_0003(1)")
    assert first.caption == "First copy"
    assert second.caption == "Second copy"
    assert first.metadata_path != second.metadata_path


def test_timestamp_prefers_photo_taken_time_over_creation_time(sample_takeout: Path) -> None:
    result = scan_album(sample_takeout)

    photo = _by_stem(result.photos, "IMG_0001")
    assert photo.timestamp_source == "photoTakenTime"
    assert photo.timestamp is not None
    assert photo.timestamp.timestamp() == 1700000000


def test_photo_without_metadata_is_flagged_unmatched_with_unknown_timestamp(
    sample_takeout: Path,
) -> None:
    result = scan_album(sample_takeout)

    photo = _by_stem(result.photos, "IMG_0004")
    assert photo.metadata_path is None
    assert photo.caption is None
    assert photo.timestamp_source == "unknown"
    assert photo.image_path in result.unmatched_images
    assert "no metadata file matched" in photo.warnings
    assert "no caption" in photo.warnings
    assert "timestamp unknown" in photo.warnings


def test_orphan_metadata_file_is_reported_as_unused(sample_takeout: Path) -> None:
    result = scan_album(sample_takeout)

    assert [p.name for p in result.unused_json_files] == ["IMG_0005.jpg.supplemental-metadata.json"]


def test_image_dimensions_are_read(sample_takeout: Path) -> None:
    result = scan_album(sample_takeout)

    photo = _by_stem(result.photos, "IMG_0001")
    assert (photo.width, photo.height) == (800, 600)
