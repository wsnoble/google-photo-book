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

# A force_solo=False panorama sharing a page gets paired with up to this
# many of the immediately-following photos, laid out as a dedicated
# full-width row for the panorama plus a second row for the companions --
# not folded into the uniform grid pattern, where it would only get a
# fraction of a row's width like any other cell.
_PANORAMA_COMPANION_COUNT = 2


@dataclass
class PageSlot:
    photo: Photo
    orientation: Orientation


@dataclass
class Page:
    slots: list[PageSlot]
    rows: list[int]  # slot count per row, e.g. [3, 2] for a 5-photo page


def _wants_solo(photo: Photo, orientation: str) -> bool:
    return orientation == "panorama" if photo.force_solo is None else bool(photo.force_solo)


def build_pages(photos: list[Photo]) -> list[Page]:
    """Lay out photos (already in book order) into pages.

    Panoramas get their own full page, shown at full frame (uncropped) --
    cropping one into a small grid cell would lose most of the image.
    Everything else is grouped into grid pages sized from a repeating
    pattern that's mostly 4-5 photos, occasionally 2, arranged into rows
    of up to 3 columns.

    A photo's force_solo overrides that automatic panorama-based decision:
    True always gives it its own page, False never does -- but a
    force_solo=False panorama still doesn't join the uniform grid pattern
    (see _take_companions / _pull_leading_companions), and force_solo=False
    more generally still won't leave an ordinary photo alone as a batch's
    leftover remainder (see _absorb_unwanted_solo_pages).
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

    index = 0
    while index < len(photos):
        photo = photos[index]
        orientation = classify_photo(photo)

        if _wants_solo(photo, orientation):
            # This forces flushing whatever's pending, but that flush is
            # incomplete (didn't reach current_target()) -- it must not
            # consume a pattern slot, or it would shift the 5/4/5/4/2
            # cadence for every page that follows it.
            flush_batch(advance_pattern=False)
            pages.append(_make_page([PageSlot(photo, orientation)]))
            index += 1
            continue

        if orientation == "panorama":
            # force_solo=False: still gets a dedicated page (a fractional
            # grid cell alongside unrelated photos would crop/shrink it
            # too much), just not alone -- paired with up to
            # _PANORAMA_COMPANION_COUNT of the immediately-following
            # photos instead. Same pattern-index treatment as the solo
            # case: doesn't consume a slot.
            panorama_slot = PageSlot(photo, orientation)
            trailing_companions, index = _take_companions(
                photos, index + 1, limit=_PANORAMA_COMPANION_COUNT
            )
            # Whatever's still pending is normally flushed to its own page
            # here -- but a force_solo=False item at the *end* of that
            # batch (closest to the panorama) would then be stranded
            # exactly like a plain solo page would (_absorb_unwanted_solo_
            # pages can't rescue it afterwards: the preceding page is
            # never a multi-photo one for a forced flush, and it doesn't
            # look forward). Claim as many trailing, force_solo=False
            # batch items as there's remaining companion budget for
            # instead of flushing them -- stopping at the first one that
            # isn't explicitly False (force_solo=None still gets forced
            # out alone, same as a solo panorama would do).
            leading_companions = _pull_leading_companions(
                batch, _PANORAMA_COMPANION_COUNT - len(trailing_companions)
            )
            flush_batch(advance_pattern=False)
            companions = leading_companions + trailing_companions
            pages.append(_make_panorama_page(panorama_slot, companions))
            continue

        batch.append(PageSlot(photo, orientation))
        if len(batch) >= current_target():
            flush_batch(advance_pattern=True)
        index += 1

    flush_batch(advance_pattern=False)
    return _absorb_unwanted_solo_pages(pages)


def _take_companions(
    photos: list[Photo], start: int, *, limit: int = _PANORAMA_COMPANION_COUNT
) -> tuple[list[PageSlot], int]:
    """Up to `limit` ordinary photos starting at index `start`, stopping
    early at one that needs its own solo/panorama handling instead (so
    it's left for the main loop, not swallowed as a mere companion).
    Returns the companion slots and the index to resume the main loop at.
    """
    companions: list[PageSlot] = []
    index = start
    while index < len(photos) and len(companions) < limit:
        candidate = photos[index]
        candidate_orientation = classify_photo(candidate)
        if _wants_solo(candidate, candidate_orientation) or candidate_orientation == "panorama":
            break
        companions.append(PageSlot(candidate, candidate_orientation))
        index += 1
    return companions, index


def _pull_leading_companions(batch: list[PageSlot], limit: int) -> list[PageSlot]:
    """Claim up to `limit` slots off the *end* of `batch` (closest to the
    panorama that's about to consume them), stopping at the first one
    (from the end) that isn't force_solo=False. Mutates `batch` in place
    to remove whatever's claimed. Order is preserved (oldest first).
    """
    count = 0
    while count < limit and count < len(batch) and batch[-(count + 1)].photo.force_solo is False:
        count += 1
    if count == 0:
        return []
    leading = batch[-count:]
    del batch[-count:]
    return leading


def _make_panorama_page(panorama_slot: PageSlot, companions: list[PageSlot]) -> Page:
    if not companions:
        return Page(slots=[panorama_slot], rows=[1])
    return Page(slots=[panorama_slot, *companions], rows=[1, len(companions)])


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

    Excludes a lone panorama (which can also reach this function with
    force_solo=False, if _take_companions found no eligible companion --
    e.g. it's the last photo in its group): merging it into an ordinary
    grid row would give it only a fraction of a cell's width, exactly what
    pairing it with companions instead of a plain solo page was meant to
    avoid. Left as a genuine full-width page in that rare case instead.

    Also excludes merging into a *preceding* panorama-plus-companions page
    (its first slot is the panorama): that page's rows are [1, N], not a
    uniform grid -- folding another slot in via _make_page() would
    recompute plain grid rows from the combined slot count, discarding the
    panorama's dedicated full-width row and squeezing it into a regular
    cell instead.
    """
    result: list[Page | None] = list(pages)
    for i, page in enumerate(pages):
        previous = result[i - 1] if i > 0 else None
        if (
            len(page.slots) == 1
            and page.slots[0].photo.force_solo is False
            and page.slots[0].orientation != "panorama"
            and previous is not None
            and len(previous.slots) > 1
            and previous.slots[0].orientation != "panorama"
        ):
            result[i - 1] = _make_page(previous.slots + page.slots)
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
