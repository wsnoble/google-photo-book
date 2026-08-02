from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from photobook.model import Photo
from photobook.ordering import order_photos


def _make_photo(name: str, timestamp: datetime | None) -> Photo:
    return Photo(
        image_path=Path(f"/album/{name}"),
        metadata_path=None,
        timestamp=timestamp,
        timestamp_source="photoTakenTime" if timestamp else "unknown",
        caption=None,
        google_photos_url=None,
        width=100,
        height=100,
        orientation=1,
        edited=False,
    )


def test_order_photos_sorts_by_timestamp() -> None:
    early = _make_photo("early.jpg", datetime(2020, 1, 1, tzinfo=UTC))
    middle = _make_photo("middle.jpg", datetime(2020, 6, 1, tzinfo=UTC))
    late = _make_photo("late.jpg", datetime(2020, 12, 1, tzinfo=UTC))

    ordered = order_photos([late, early, middle])

    assert [p.image_path.name for p in ordered] == ["early.jpg", "middle.jpg", "late.jpg"]


def test_order_photos_appends_unknown_timestamps_at_the_end() -> None:
    dated = _make_photo("dated.jpg", datetime(2020, 1, 1, tzinfo=UTC))
    undated_a = _make_photo("undated_a.jpg", None)
    undated_b = _make_photo("undated_b.jpg", None)

    ordered = order_photos([undated_a, dated, undated_b])

    assert [p.image_path.name for p in ordered] == ["dated.jpg", "undated_a.jpg", "undated_b.jpg"]


def test_manual_order_overrides_timestamp_order_for_matched_photos() -> None:
    a = _make_photo("a.jpg", datetime(2020, 1, 1, tzinfo=UTC))
    b = _make_photo("b.jpg", datetime(2020, 2, 1, tzinfo=UTC))
    c = _make_photo("c.jpg", datetime(2020, 3, 1, tzinfo=UTC))

    # Deliberately non-chronological, like a manually curated album sequence.
    manual_order = ["/album/c.jpg", "/album/a.jpg", "/album/b.jpg"]
    ordered = order_photos([a, b, c], manual_order=manual_order)

    assert [p.image_path.name for p in ordered] == ["c.jpg", "a.jpg", "b.jpg"]


def test_manual_order_interpolates_unlisted_photos_by_timestamp() -> None:
    jan = _make_photo("jan.jpg", datetime(2020, 1, 1, tzinfo=UTC))
    mar = _make_photo("mar.jpg", datetime(2020, 3, 1, tzinfo=UTC))
    may = _make_photo("may.jpg", datetime(2020, 5, 1, tzinfo=UTC))
    # Not in manual_order; timestamp falls between jan and mar.
    feb = _make_photo("feb.jpg", datetime(2020, 2, 1, tzinfo=UTC))

    manual_order = ["/album/jan.jpg", "/album/mar.jpg", "/album/may.jpg"]
    ordered = order_photos([may, feb, jan, mar], manual_order=manual_order)

    assert [p.image_path.name for p in ordered] == ["jan.jpg", "feb.jpg", "mar.jpg", "may.jpg"]


def test_manual_order_appends_undated_unlisted_photos_at_the_end() -> None:
    jan = _make_photo("jan.jpg", datetime(2020, 1, 1, tzinfo=UTC))
    mar = _make_photo("mar.jpg", datetime(2020, 3, 1, tzinfo=UTC))
    mystery = _make_photo("mystery.jpg", None)

    manual_order = ["/album/mar.jpg", "/album/jan.jpg"]
    ordered = order_photos([mystery, jan, mar], manual_order=manual_order)

    assert [p.image_path.name for p in ordered] == ["mar.jpg", "jan.jpg", "mystery.jpg"]
