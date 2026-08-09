from __future__ import annotations

from pathlib import Path

from photobook.layout import _split_into_rows, build_pages
from photobook.model import Photo


def _make_photo(name: str, width: int, height: int, *, force_solo: bool | None = None) -> Photo:
    return Photo(
        image_path=Path(f"/album/{name}"),
        metadata_path=None,
        timestamp=None,
        timestamp_source="unknown",
        caption=None,
        google_photos_url=None,
        width=width,
        height=height,
        orientation=1,
        edited=False,
        force_solo=force_solo,
    )


def _landscape(name: str, *, force_solo: bool | None = None) -> Photo:
    return _make_photo(name, 800, 600, force_solo=force_solo)


def _panorama(name: str, *, force_solo: bool | None = None) -> Photo:
    return _make_photo(name, 2400, 800, force_solo=force_solo)


def _names_per_page(pages) -> list[list[str]]:
    return [[slot.photo.image_path.name for slot in page.slots] for page in pages]


def test_split_into_rows_five_is_three_and_two() -> None:
    assert _split_into_rows(5) == [3, 2]


def test_split_into_rows_four_is_two_and_two() -> None:
    assert _split_into_rows(4) == [2, 2]


def test_split_into_rows_two_or_fewer_is_a_single_row() -> None:
    assert _split_into_rows(2) == [2]
    assert _split_into_rows(1) == [1]
    assert _split_into_rows(0) == []


def test_split_into_rows_three_is_forced_into_two_rows() -> None:
    # A single row of 3 spanning the full page height makes each cell far
    # taller than wide (aspect ratio ~0.37) -- either heavily cropped
    # (cover-fit) or shrunk to a sliver with lots of empty space
    # (contain-fit). [2, 1] gives each row a much more reasonable shape.
    assert _split_into_rows(3) == [2, 1]


def test_split_into_rows_six_and_seven_are_unaffected_by_the_three_row_rule() -> None:
    # These already split into 2+ rows on their own (row_count != 1 before
    # the three-specific override), so the forced-second-row rule for a
    # lone row of 3 doesn't change anything here.
    assert _split_into_rows(6) == [3, 3]
    assert _split_into_rows(7) == [3, 2, 2]


def test_pages_follow_the_size_pattern_5_4_5_4_2() -> None:
    photos = [_landscape(f"p{i}.jpg") for i in range(20)]
    pages = build_pages(photos)
    assert [len(page.slots) for page in pages] == [5, 4, 5, 4, 2]


def test_pattern_repeats_and_a_short_remainder_forms_its_own_page() -> None:
    photos = [_landscape(f"p{i}.jpg") for i in range(23)]
    pages = build_pages(photos)
    # 5 + 4 + 5 + 4 + 2 = 20, then the pattern restarts: 3 left over.
    assert [len(page.slots) for page in pages] == [5, 4, 5, 4, 2, 3]


def test_panorama_gets_its_own_page_without_disrupting_the_pattern() -> None:
    photos = [_landscape("a.jpg"), _panorama("wide.jpg"), _landscape("b.jpg"), _landscape("c.jpg")]
    pages = build_pages(photos)
    # The pending 1-photo batch is flushed before the panorama's solo page,
    # and the pattern's first slot (size 5) isn't consumed by either.
    assert _names_per_page(pages) == [["a.jpg"], ["wide.jpg"], ["b.jpg", "c.jpg"]]
    assert len(pages[1].slots) == 1
    assert pages[1].slots[0].orientation == "panorama"


def test_panorama_forced_flush_does_not_shift_the_pattern_index() -> None:
    # Regression test: flush_batch() used to always advance the pattern
    # index, even for an incomplete batch forced out by a panorama. That
    # shifted _PAGE_SIZE_PATTERN for every page after the panorama instead
    # of leaving the cadence untouched.
    photos = [_landscape("pre.jpg"), _panorama("wide.jpg")] + [
        _landscape(f"p{i}.jpg") for i in range(20)
    ]
    pages = build_pages(photos)
    sizes = [len(page.slots) for page in pages]
    # "pre.jpg" is forced out alone (doesn't reach the target of 5), then
    # the panorama's own page, then the full pattern starts fresh at 5 --
    # not offset by the earlier incomplete flush.
    assert sizes == [1, 1, 5, 4, 5, 4, 2]


def test_solo_page_has_a_single_row() -> None:
    pages = build_pages([_panorama("wide.jpg")])
    assert pages[0].rows == [1]


def test_empty_photo_list_produces_no_pages() -> None:
    assert build_pages([]) == []


def test_force_solo_true_gives_an_ordinary_photo_its_own_page() -> None:
    photos = [_landscape("a.jpg"), _landscape("b.jpg", force_solo=True), _landscape("c.jpg")]

    pages = build_pages(photos)

    assert _names_per_page(pages) == [["a.jpg"], ["b.jpg"], ["c.jpg"]]


def test_force_solo_false_panorama_is_paired_with_companions_not_squeezed_into_the_grid() -> None:
    photos = [_landscape("a.jpg"), _panorama("wide.jpg", force_solo=False), _landscape("b.jpg")]

    pages = build_pages(photos)

    # "wide.jpg" still doesn't join the uniform grid batch (a fractional
    # cell width would crop/shrink it too much) -- it gets a dedicated
    # page instead, paired with the next photo. "a.jpg" was the only thing
    # pending when the panorama interrupted the batch, so it's forced out
    # onto its own page first (same as a solo panorama would do).
    assert _names_per_page(pages) == [["a.jpg"], ["wide.jpg", "b.jpg"]]
    panorama_page = pages[1]
    assert panorama_page.rows == [1, 1]
    assert panorama_page.slots[0].photo.image_path.name == "wide.jpg"


def test_force_solo_false_panorama_pairs_with_up_to_two_companions() -> None:
    photos = [
        _panorama("wide.jpg", force_solo=False),
        _landscape("b.jpg"),
        _landscape("c.jpg"),
        _landscape("d.jpg"),
    ]

    pages = build_pages(photos)

    # Only 2 companions max, even though a 3rd ("d.jpg") was available and
    # ordinarily eligible.
    assert _names_per_page(pages) == [["wide.jpg", "b.jpg", "c.jpg"], ["d.jpg"]]
    assert pages[0].rows == [1, 2]


def test_panorama_companion_pairing_stops_at_another_special_photo() -> None:
    # "c.jpg" (also a panorama) must not be swallowed as a mere companion
    # -- it needs its own solo/pairing treatment via the main loop.
    photos = [
        _panorama("wide.jpg", force_solo=False),
        _landscape("b.jpg"),
        _panorama("also_wide.jpg"),
        _landscape("d.jpg"),
    ]

    pages = build_pages(photos)

    assert _names_per_page(pages) == [["wide.jpg", "b.jpg"], ["also_wide.jpg"], ["d.jpg"]]


def test_force_solo_false_panorama_with_no_available_companion_stays_alone() -> None:
    # The panorama is the last photo -- no companion available. Unlike an
    # ordinary force_solo=False photo, this must NOT be merged into the
    # preceding grid page by _absorb_unwanted_solo_pages (that would just
    # crop/shrink it into a fractional cell, the exact thing pairing was
    # meant to avoid) -- it stays a genuine full-width solo page instead.
    photos = [_landscape(f"p{i}.jpg") for i in range(4)] + [_panorama("wide.jpg", force_solo=False)]

    pages = build_pages(photos)

    assert _names_per_page(pages) == [["p0.jpg", "p1.jpg", "p2.jpg", "p3.jpg"], ["wide.jpg"]]
    assert pages[-1].rows == [1]


def test_force_solo_false_merges_a_leftover_page_into_the_previous_page() -> None:
    # 5 + 4 + 5 + 4 + 2 = 20, then 1 left over -- normally its own page.
    photos = [_landscape(f"p{i}.jpg") for i in range(20)] + [
        _landscape("last.jpg", force_solo=False)
    ]

    pages = build_pages(photos)

    # The lone leftover joins the last grid page (2 -> 3) instead of
    # getting a page to itself.
    assert [len(page.slots) for page in pages] == [5, 4, 5, 4, 3]
    assert pages[-1].slots[-1].photo.image_path.name == "last.jpg"


def test_force_solo_false_photo_stranded_before_a_panorama_becomes_its_leading_companion() -> None:
    # Regression test: a solo panorama (force_solo=True) flushes the batch
    # right before it, so a single force_solo=False photo left pending at
    # that moment used to get flushed to its own page -- and
    # _absorb_unwanted_solo_pages couldn't rescue it afterwards, since the
    # preceding page (the solo panorama) is also single-photo. It must
    # instead join the *next* panorama's companion row.
    photos = [
        _panorama("first_wide.jpg", force_solo=True),
        _landscape("stranded.jpg", force_solo=False),
        _panorama("second_wide.jpg", force_solo=False),
        _landscape("companion.jpg"),
    ]

    pages = build_pages(photos)

    assert _names_per_page(pages) == [
        ["first_wide.jpg"],
        ["second_wide.jpg", "stranded.jpg", "companion.jpg"],
    ]
    assert pages[1].rows == [1, 2]


def test_force_solo_false_panorama_at_the_end_pulls_leading_companions_from_the_batch() -> None:
    # Regression test: with no photo left after it (e.g. the panorama is
    # the last photo in its chapter), _take_companions finds nothing --
    # but two force_solo=False photos were sitting in the pending batch
    # right in front of it and must be pulled in as leading companions
    # instead of being flushed as their own page, leaving the panorama
    # stranded alone.
    photos = [
        _landscape("a.jpg", force_solo=False),
        _landscape("b.jpg", force_solo=False),
        _panorama("wide.jpg", force_solo=False),
    ]

    pages = build_pages(photos)

    assert _names_per_page(pages) == [["wide.jpg", "a.jpg", "b.jpg"]]
    assert pages[0].rows == [1, 2]


def test_force_solo_false_panorama_only_pulls_force_solo_false_batch_items() -> None:
    # A batch item that isn't explicitly force_solo=False (force_solo=None
    # here) stops the pull, same as it would if it were the sole pending
    # item -- it's forced out onto its own page instead of being swept in
    # as a companion just because it happened to be adjacent.
    photos = [
        _landscape("a.jpg"),
        _landscape("b.jpg", force_solo=False),
        _panorama("wide.jpg", force_solo=False),
    ]

    pages = build_pages(photos)

    assert _names_per_page(pages) == [["a.jpg"], ["wide.jpg", "b.jpg"]]


def test_force_solo_false_photo_with_no_neighboring_grid_page_stays_alone() -> None:
    # A documented limitation, not a bug: force_solo=False means "don't
    # leave this alone if there's a neighboring grid page to join" -- if
    # it's the only photo in its group, there's nothing to merge into.
    pages = build_pages([_landscape("only.jpg", force_solo=False)])

    assert len(pages) == 1
    assert len(pages[0].slots) == 1
