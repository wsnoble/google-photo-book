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
        if orientation == "panorama":
            # A panorama forces flushing whatever's pending, but that
            # flush is incomplete (didn't reach current_target()) -- it
            # must not consume a pattern slot, or a panorama would shift
            # the 5/4/5/4/2 cadence for every page that follows it.
            flush_batch(advance_pattern=False)
            pages.append(_make_page([PageSlot(photo, orientation)]))
            continue

        batch.append(PageSlot(photo, orientation))
        if len(batch) >= current_target():
            flush_batch(advance_pattern=True)

    flush_batch(advance_pattern=False)
    return pages


def _make_page(slots: list[PageSlot]) -> Page:
    return Page(slots=slots, rows=_split_into_rows(len(slots)))


def _split_into_rows(n: int, max_columns: int = _MAX_ROW_COLUMNS) -> list[int]:
    """Split n slots into rows of at most max_columns, as evenly sized as
    possible (5 -> [3, 2], 4 -> [2, 2], 7 -> [3, 2, 2])."""
    if n <= max_columns:
        return [n] if n > 0 else []
    row_count = math.ceil(n / max_columns)
    base, remainder = divmod(n, row_count)
    return [base + 1 if i < remainder else base for i in range(row_count)]
