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


def test_manual_order_appends_unlisted_photos_at_the_end_sorted_by_timestamp() -> None:
    # A manually-curated album order is not chronologically local (this
    # sequence deliberately jumps Nov -> Feb -> Jun), so a photo missing
    # from manual_order must NOT be guessed into a slot next to whichever
    # placed photo happens to have the closest timestamp — that produced a
    # confidently wrong position in practice. It goes to the end instead,
    # sorted among the other unlisted photos, as an honest "unknown."
    nov = _make_photo("nov.jpg", datetime(2017, 11, 1, tzinfo=UTC))
    feb = _make_photo("feb.jpg", datetime(2017, 2, 1, tzinfo=UTC))
    jun = _make_photo("jun.jpg", datetime(2017, 6, 1, tzinfo=UTC))
    # Not in manual_order. Chronologically nearest to feb, but must still
    # land at the end, not interpolated next to feb.
    mar = _make_photo("mar.jpg", datetime(2017, 3, 1, tzinfo=UTC))
    aug = _make_photo("aug.jpg", datetime(2017, 8, 1, tzinfo=UTC))

    manual_order = ["/album/nov.jpg", "/album/feb.jpg", "/album/jun.jpg"]
    ordered = order_photos([aug, jun, mar, nov, feb], manual_order=manual_order)

    assert [p.image_path.name for p in ordered] == [
        "nov.jpg",
        "feb.jpg",
        "jun.jpg",
        "mar.jpg",
        "aug.jpg",
    ]


def test_manual_order_appends_undated_unlisted_photos_last_of_all() -> None:
    jan = _make_photo("jan.jpg", datetime(2020, 1, 1, tzinfo=UTC))
    mar = _make_photo("mar.jpg", datetime(2020, 3, 1, tzinfo=UTC))
    dated_leftover = _make_photo("dated_leftover.jpg", datetime(2020, 2, 1, tzinfo=UTC))
    mystery = _make_photo("mystery.jpg", None)

    manual_order = ["/album/mar.jpg", "/album/jan.jpg"]
    ordered = order_photos([mystery, jan, dated_leftover, mar], manual_order=manual_order)

    assert [p.image_path.name for p in ordered] == [
        "mar.jpg",
        "jan.jpg",
        "dated_leftover.jpg",
        "mystery.jpg",
    ]


def test_guess_leftover_positions_inserts_next_to_nearest_timestamp() -> None:
    jan = _make_photo("jan.jpg", datetime(2020, 1, 1, tzinfo=UTC))
    mar = _make_photo("mar.jpg", datetime(2020, 3, 1, tzinfo=UTC))
    may = _make_photo("may.jpg", datetime(2020, 5, 1, tzinfo=UTC))
    # Not in manual_order; chronologically closest to mar (28 days away),
    # not jan (31 days) or may (61 days).
    feb = _make_photo("feb.jpg", datetime(2020, 2, 2, tzinfo=UTC))

    manual_order = ["/album/jan.jpg", "/album/mar.jpg", "/album/may.jpg"]
    ordered = order_photos(
        [may, feb, jan, mar], manual_order=manual_order, guess_leftover_positions=True
    )

    assert [p.image_path.name for p in ordered] == ["jan.jpg", "feb.jpg", "mar.jpg", "may.jpg"]


def test_guess_leftover_positions_still_appends_undated_leftovers_last() -> None:
    jan = _make_photo("jan.jpg", datetime(2020, 1, 1, tzinfo=UTC))
    mar = _make_photo("mar.jpg", datetime(2020, 3, 1, tzinfo=UTC))
    mystery = _make_photo("mystery.jpg", None)

    manual_order = ["/album/jan.jpg", "/album/mar.jpg"]
    ordered = order_photos(
        [mystery, jan, mar], manual_order=manual_order, guess_leftover_positions=True
    )

    assert [p.image_path.name for p in ordered] == ["jan.jpg", "mar.jpg", "mystery.jpg"]


def test_guess_leftover_positions_can_place_photo_far_from_true_position() -> None:
    # Regression/documentation test: this is the exact failure mode found
    # in production. The manual order is not chronologically local (jumps
    # Nov -> Feb -> Jun), so even *correct* nearest-neighbor insertion
    # confidently places `mar` next to `feb` — which is wrong if `mar`'s
    # true manually-curated position was actually much later in the
    # sequence. This test documents that `guess_leftover_positions=True`
    # is a real trade-off, not a free upgrade over the default.
    nov = _make_photo("nov.jpg", datetime(2017, 11, 1, tzinfo=UTC))
    feb = _make_photo("feb.jpg", datetime(2017, 2, 1, tzinfo=UTC))
    jun = _make_photo("jun.jpg", datetime(2017, 6, 1, tzinfo=UTC))
    mar = _make_photo("mar.jpg", datetime(2017, 3, 1, tzinfo=UTC))

    manual_order = ["/album/nov.jpg", "/album/feb.jpg", "/album/jun.jpg"]
    ordered = order_photos(
        [jun, mar, nov, feb], manual_order=manual_order, guess_leftover_positions=True
    )

    assert [p.image_path.name for p in ordered] == ["nov.jpg", "feb.jpg", "mar.jpg", "jun.jpg"]
