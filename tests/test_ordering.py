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
