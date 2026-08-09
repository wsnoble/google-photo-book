from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from photobook.chapters import assign_countries, group_into_chapters, take_divider_photos
from photobook.model import Photo

_ROME = (41.9028, 12.4964)
_PARIS = (48.8566, 2.3522)


def _make_photo(
    name: str,
    *,
    latitude: float | None = None,
    longitude: float | None = None,
    timestamp: datetime | None = None,
    width: int = 800,
    height: int = 600,
    force_solo: bool | None = None,
) -> Photo:
    return Photo(
        image_path=Path(f"/album/{name}"),
        metadata_path=None,
        timestamp=timestamp,
        timestamp_source="photoTakenTime" if timestamp else "unknown",
        caption=None,
        google_photos_url=None,
        width=width,
        height=height,
        orientation=1,
        edited=False,
        latitude=latitude,
        longitude=longitude,
        force_solo=force_solo,
    )


def _panorama(name: str, *, force_solo: bool | None = None) -> Photo:
    return _make_photo(name, width=2400, height=800, force_solo=force_solo)


def test_geotagged_photos_get_their_real_country() -> None:
    rome = _make_photo("rome.jpg", latitude=_ROME[0], longitude=_ROME[1])
    paris = _make_photo("paris.jpg", latitude=_PARIS[0], longitude=_PARIS[1])

    countries = assign_countries([rome, paris])

    assert countries == ["Italy", "France"]


def test_photo_without_gps_inherits_nearest_timestamp_neighbors_country() -> None:
    t0 = datetime(2024, 6, 1, tzinfo=UTC)
    rome = _make_photo("rome.jpg", latitude=_ROME[0], longitude=_ROME[1], timestamp=t0)
    paris = _make_photo(
        "paris.jpg", latitude=_PARIS[0], longitude=_PARIS[1], timestamp=t0 + timedelta(days=10)
    )
    # Much closer in time to `rome` (1 hour away) than to `paris` (10 days away).
    undated_gps_loss = _make_photo("screenshot.jpg", timestamp=t0 + timedelta(hours=1))

    countries = assign_countries([rome, paris, undated_gps_loss])

    assert countries == ["Italy", "France", "Italy"]


def test_photo_with_neither_gps_nor_timestamp_gets_none() -> None:
    rome = _make_photo("rome.jpg", latitude=_ROME[0], longitude=_ROME[1])
    mystery = _make_photo("mystery.jpg")

    countries = assign_countries([rome, mystery])

    assert countries == ["Italy", None]


def test_inheritance_donor_pool_is_geotagged_photos_only_not_growing() -> None:
    # rome and paris are 100 days apart. `near_rome` (day 49) and
    # `near_paris` (day 51) are each objectively closer to one real donor
    # than the other (49 < 51 either way) -- but only 2 days apart from
    # each other. If the donor pool grew to include already-inherited
    # photos as the loop progresses, processing `near_rome` first (day 49,
    # correctly resolves to Italy) then `near_paris` next (day 51) could
    # let `near_paris` find `near_rome` as its "nearest donor" (2 days
    # away) instead of comparing against the real geotagged photos
    # directly (49/51 days away) -- incorrectly inheriting Italy instead
    # of the correct France. Assert the fixed-donor-pool behavior: both
    # resolve independently against the real donors only.
    t0 = datetime(2024, 6, 1, tzinfo=UTC)
    rome = _make_photo("rome.jpg", latitude=_ROME[0], longitude=_ROME[1], timestamp=t0)
    paris = _make_photo(
        "paris.jpg", latitude=_PARIS[0], longitude=_PARIS[1], timestamp=t0 + timedelta(days=100)
    )
    near_rome = _make_photo("near_rome.jpg", timestamp=t0 + timedelta(days=49))
    near_paris = _make_photo("near_paris.jpg", timestamp=t0 + timedelta(days=51))

    countries = assign_countries([rome, paris, near_rome, near_paris])

    assert countries == ["Italy", "France", "Italy", "France"]


def test_no_geotagged_photos_at_all_returns_all_none() -> None:
    photos = [_make_photo("a.jpg"), _make_photo("b.jpg", timestamp=datetime.now(UTC))]

    countries = assign_countries(photos)

    assert countries == [None, None]


def test_group_into_chapters_groups_contiguous_runs() -> None:
    photos = [_make_photo(n) for n in ("a", "b", "c", "d", "e")]
    countries = ["Italy", "Italy", None, "Italy", "France"]

    groups = group_into_chapters(photos, countries)

    assert [(country, [p.image_path.name for p in group]) for country, group in groups] == [
        ("Italy", ["a", "b"]),
        (None, ["c"]),
        ("Italy", ["d"]),
        ("France", ["e"]),
    ]


def _names(photos: list[Photo]) -> list[str]:
    return [p.image_path.name for p in photos]


def test_take_divider_photos_without_a_panorama_takes_up_to_three() -> None:
    photos = [_make_photo(n) for n in ("a", "b", "c", "d")]

    divider, remaining = take_divider_photos(photos)

    assert _names(divider) == ["a", "b", "c"]
    assert _names(remaining) == ["d"]


def test_take_divider_photos_stops_at_a_force_solo_true_photo() -> None:
    # Regression test: an early ineligible photo must stop selection
    # rather than being skipped over -- pulling "b"/"c" onto the divider
    # ahead of "a" would render the book as b, c, a instead of a, b, c.
    photos = [_make_photo("a", force_solo=True), _make_photo("b"), _make_photo("c")]

    divider, remaining = take_divider_photos(photos)

    assert _names(divider) == []
    assert _names(remaining) == ["a", "b", "c"]


def test_take_divider_photos_gives_a_leading_panorama_the_bottom_row_plus_one_companion() -> None:
    photos = [_panorama("wide"), _make_photo("b"), _make_photo("c"), _make_photo("d")]

    divider, remaining = take_divider_photos(photos)

    # Panorama costs 2 quadrant-units, leaving room for exactly 1 more.
    assert _names(divider) == ["wide", "b"]
    assert _names(remaining) == ["c", "d"]


def test_take_divider_photos_finds_a_panorama_appearing_after_one_ordinary_photo() -> None:
    photos = [_make_photo("a"), _panorama("wide"), _make_photo("c"), _make_photo("d")]

    divider, remaining = take_divider_photos(photos)

    # "a" (cost 1) + "wide" (cost 2) exactly exhausts the budget of 3.
    assert _names(divider) == ["a", "wide"]
    assert _names(remaining) == ["c", "d"]


def test_take_divider_photos_skips_a_panorama_if_budget_already_spent() -> None:
    photos = [_make_photo("a"), _make_photo("b"), _make_photo("c"), _panorama("wide")]

    divider, remaining = take_divider_photos(photos)

    # By the time "wide" is reached, all 3 quadrant-units are already
    # spent on ordinary photos -- it's left for build_pages() instead,
    # which will pair it with companions on a later page.
    assert _names(divider) == ["a", "b", "c"]
    assert _names(remaining) == ["wide"]


def test_take_divider_photos_never_takes_a_second_panorama() -> None:
    photos = [_panorama("wide1"), _panorama("wide2"), _make_photo("c")]

    divider, remaining = take_divider_photos(photos)

    # "wide1" spends 2 of the 3 quadrant-units; "wide2" is a second
    # panorama, never eligible regardless of remaining budget -- and,
    # like any ineligible photo, stops selection there rather than being
    # skipped in favor of "c" (which would otherwise still fit).
    assert _names(divider) == ["wide1"]
    assert _names(remaining) == ["wide2", "c"]


def test_take_divider_photos_stops_at_a_force_solo_true_panorama() -> None:
    photos = [_panorama("wide", force_solo=True), _make_photo("b"), _make_photo("c")]

    divider, remaining = take_divider_photos(photos)

    assert _names(divider) == []
    assert _names(remaining) == ["wide", "b", "c"]
