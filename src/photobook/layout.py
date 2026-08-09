from __future__ import annotations

import math
from dataclasses import dataclass

from photobook.classify import Orientation, classify_photo
from photobook.model import Photo

# Cycle of grid-page sizes: mostly 4-5 photos per page, occasionally 2, for
# visual variety (roughly 1 in 5 pages is a pair). Adjust this tuple to
# change the mix.
_PAGE_SIZE_PATTERN = (5, 4, 5, 4, 2)
_MAX_ROW_COLUMNS = 3


@dataclass
class PageSlot:
    photo: Photo
    orientation: Orientation


@dataclass
class Page:
    slots: list[PageSlot]
    rows: list[int]  # slot count per row, e.g. [3, 2] for a 5-photo page


def build_pages(photos: list[Photo]) -> list[Page]:
    """Lay out photos (already in book order) into pages.

    Panoramas get their own full page, shown at full frame (uncropped) --
    cropping one into a small grid cell would lose most of the image.
    Everything else is grouped into grid pages sized from a repeating
    pattern that's mostly 4-5 photos, occasionally 2, arranged into rows
    of up to 3 columns.

    A photo's force_solo overrides that automatic panorama-based decision:
    True always gives it its own page, False never does, even if it's a
    panorama or would otherwise be left alone as a batch's leftover
    remainder (see _absorb_unwanted_solo_pages).
    """
    pages: list[Page] = []
    batch: list[PageSlot] = []
    pattern_index = 0

    def current_target() -> int:
        return _PAGE_SIZE_PATTERN[pattern_index % len(_PAGE_SIZE_PATTERN)]

    def flush_batch(*, advance_pattern: bool) -> None:
        nonlocal batch, pattern_index
        if batch:
            pages.append(_make_page(batch))
            batch = []
            if advance_pattern:
                pattern_index += 1

    for photo in photos:
        orientation = classify_photo(photo)
        wants_solo = orientation == "panorama" if photo.force_solo is None else photo.force_solo
        if wants_solo:
            # This forces flushing whatever's pending, but that flush is
            # incomplete (didn't reach current_target()) -- it must not
            # consume a pattern slot, or it would shift the 5/4/5/4/2
            # cadence for every page that follows it.
            flush_batch(advance_pattern=False)
            pages.append(_make_page([PageSlot(photo, orientation)]))
            continue

        batch.append(PageSlot(photo, orientation))
        if len(batch) >= current_target():
            flush_batch(advance_pattern=True)

    flush_batch(advance_pattern=False)
    return _absorb_unwanted_solo_pages(pages)


def _absorb_unwanted_solo_pages(pages: list[Page]) -> list[Page]:
    """A photo with force_solo=False can still end up alone on a page --
    e.g. it's the last item left over after the 5/4/5/4/2 pattern runs
    out, unrelated to panorama detection -- so merge any such page into
    the preceding grid page rather than leaving it alone, since
    force_solo=False means "never solo," not just "don't treat as a
    panorama." The only case this can arise in is a trailing leftover (a
    forced flush always produces a page for just the forcing photo, so an
    immediately adjacent page is never a multi-photo one to merge into) --
    if there's no preceding grid page either (e.g. it's the only photo in
    its group), it's left alone; there's nothing to merge it into.
    """
    result: list[Page | None] = list(pages)
    for i, page in enumerate(pages):
        if (
            len(page.slots) == 1
            and page.slots[0].photo.force_solo is False
            and i > 0
            and result[i - 1] is not None
            and len(result[i - 1].slots) > 1
        ):
            result[i - 1] = _make_page(result[i - 1].slots + page.slots)
            result[i] = None
    return [page for page in result if page is not None]


def _make_page(slots: list[PageSlot]) -> Page:
    return Page(slots=slots, rows=_split_into_rows(len(slots)))


_MAX_SINGLE_ROW_COLUMNS = 2


def _split_into_rows(n: int, max_columns: int = _MAX_ROW_COLUMNS) -> list[int]:
    """Split n slots into rows of at most max_columns, as evenly sized as
    possible (5 -> [3, 2], 4 -> [2, 2], 7 -> [3, 2, 2]).

    A row of 3+ columns is fine when it's one of several rows on a page
    (each row is only a fraction of the page height, so cells stay a
    reasonable shape) but not as a page's *only* row: 3 columns at the
    full page height makes each cell far taller than wide, which either
    crops badly (cover-fit) or shrinks the photo to a sliver with lots of
    empty space (contain-fit). n<=max_columns would otherwise return a
    single such row, so force a second row instead when that would happen.
    """
    if n <= 0:
        return []
    if n <= _MAX_SINGLE_ROW_COLUMNS:
        return [n]
    row_count = math.ceil(n / max_columns)
    if row_count == 1:
        row_count = 2
    base, remainder = divmod(n, row_count)
    return [base + 1 if i < remainder else base for i in range(row_count)]
