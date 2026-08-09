from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

from photobook.model import Photo
from photobook.review import load_review_file
from photobook.review_export import export_review_file

_ROME = (41.9028, 12.4964)


def _make_photo(
    name: str,
    *,
    timestamp: datetime | None = None,
    caption: str | None = None,
    width: int = 800,
    height: int = 600,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Photo:
    return Photo(
        image_path=Path(f"/album/{name}"),
        metadata_path=None,
        timestamp=timestamp,
        timestamp_source="photoTakenTime" if timestamp else "unknown",
        caption=caption,
        google_photos_url=None,
        width=width,
        height=height,
        orientation=1,
        edited=False,
        latitude=latitude,
        longitude=longitude,
    )


def _read_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def test_orders_by_timestamp_with_undated_photos_last(tmp_path: Path) -> None:
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    later = _make_photo("later.jpg", timestamp=t0 + timedelta(days=1))
    earlier = _make_photo("earlier.jpg", timestamp=t0)
    undated = _make_photo("undated.jpg")
    output = tmp_path / "review.tsv"

    export_review_file([later, undated, earlier], output)

    rows = [r for r in _read_rows(output) if r["row_type"] == "photo"]
    assert [r["filename"] for r in rows] == ["earlier.jpg", "later.jpg", "undated.jpg"]


def test_chapter_rows_are_inserted_by_country(tmp_path: Path) -> None:
    photo = _make_photo(
        "rome.jpg", timestamp=datetime.now(UTC), latitude=_ROME[0], longitude=_ROME[1]
    )
    output = tmp_path / "review.tsv"

    export_review_file([photo], output)

    rows = _read_rows(output)
    assert [r["row_type"] for r in rows] == ["chapter", "photo"]
    assert rows[0]["chapter_title"] == "Italy"


def test_existing_caption_is_carried_over_uncaptioned_left_blank(tmp_path: Path) -> None:
    captioned = _make_photo("a.jpg", timestamp=datetime.now(UTC), caption="A real caption")
    uncaptioned = _make_photo("b.jpg", timestamp=datetime.now(UTC) + timedelta(seconds=1))
    output = tmp_path / "review.tsv"

    export_review_file([captioned, uncaptioned], output)

    rows = {r["filename"]: r for r in _read_rows(output) if r["row_type"] == "photo"}
    assert rows["a.jpg"]["tag"] == "A real caption"
    assert rows["b.jpg"]["tag"] == ""


def test_solo_column_reflects_a_panorama_landing_alone(tmp_path: Path) -> None:
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    panorama = _make_photo("wide.jpg", timestamp=t0, width=2400, height=800)
    # Two ordinary photos so they land together on a real grid page rather
    # than one of them also becoming an incidental trailing-leftover solo
    # page (a real, separate case -- see layout.py's leftover-of-1
    # behavior -- not what this test is checking).
    landscape_a = _make_photo("a.jpg", timestamp=t0 + timedelta(seconds=1))
    landscape_b = _make_photo("b.jpg", timestamp=t0 + timedelta(seconds=2))
    output = tmp_path / "review.tsv"

    export_review_file([panorama, landscape_a, landscape_b], output)

    rows = {r["filename"]: r for r in _read_rows(output) if r["row_type"] == "photo"}
    assert rows["wide.jpg"]["solo"] == "true"
    assert rows["a.jpg"]["solo"] == ""
    assert rows["b.jpg"]["solo"] == ""


def test_exported_file_loads_back_via_load_review_file(tmp_path: Path) -> None:
    photos = [
        _make_photo("rome.jpg", timestamp=datetime.now(UTC), latitude=_ROME[0], longitude=_ROME[1]),
        _make_photo("undated.jpg"),
    ]
    output = tmp_path / "review.tsv"

    export_review_file(photos, output)
    groups = load_review_file(output, photos)

    assert sum(len(group_photos) for _, group_photos in groups) == 2


def test_repeated_country_after_a_none_gap_gets_its_own_chapter_row(tmp_path: Path) -> None:
    # Regression test: group_into_chapters produces three separate groups
    # here (Italy, None, Italy) -- each needs its own row in the exported
    # file, even though the *visible* divider only renders once for the
    # repeated title. Deduping in the writer (as if only a title change
    # mattered) would make load_review_file merge these back into one
    # group, changing which photos share a build_pages() pattern-reset
    # scope and silently invalidating the `solo` column's predictions,
    # which are computed against the real (undeduped) group boundaries.
    # No photo here has a timestamp, so order_photos (all-undated ->
    # preserve input order) can't reshuffle this sequence out from under
    # the test.
    rome_a = _make_photo("rome_a.jpg", latitude=_ROME[0], longitude=_ROME[1])
    rome_b = _make_photo("rome_b.jpg", latitude=_ROME[0], longitude=_ROME[1])
    gap = _make_photo("gap.jpg")
    rome_c = _make_photo("rome_c.jpg", latitude=_ROME[0], longitude=_ROME[1])
    photos = [rome_a, rome_b, gap, rome_c]
    output = tmp_path / "review.tsv"

    export_review_file(photos, output)

    chapter_rows = [r for r in _read_rows(output) if r["row_type"] == "chapter"]
    assert [r["chapter_title"] for r in chapter_rows] == ["Italy", "", "Italy"]

    groups = load_review_file(output, photos)
    assert [(country, [p.image_path.name for p in group]) for country, group in groups] == [
        ("Italy", ["rome_a.jpg", "rome_b.jpg"]),
        (None, ["gap.jpg"]),
        ("Italy", ["rome_c.jpg"]),
    ]
