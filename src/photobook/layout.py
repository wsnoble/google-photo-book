from __future__ import annotations

from dataclasses import dataclass

from photobook.classify import Orientation, classify_photo
from photobook.model import Photo


@dataclass
class PageSlot:
    photo: Photo
    orientation: Orientation


@dataclass
class Page:
    slots: list[PageSlot]


def build_pages(photos: list[Photo]) -> list[Page]:
    """Lay out photos (already in book order) into pages.

    -   Landscape, panorama, and square photos: one per page.
    -   Portraits: paired two-per-page with the next portrait in sequence;
        an odd one out (no portrait immediately follows) gets its own page
        rather than waiting arbitrarily far ahead for a pairing partner,
        so pairing never reorders photos.
    """
    pages: list[Page] = []
    pending_portrait: PageSlot | None = None

    def flush_pending() -> None:
        nonlocal pending_portrait
        if pending_portrait is not None:
            pages.append(Page(slots=[pending_portrait]))
            pending_portrait = None

    for photo in photos:
        orientation = classify_photo(photo)
        slot = PageSlot(photo=photo, orientation=orientation)

        if orientation == "portrait":
            if pending_portrait is None:
                pending_portrait = slot
            else:
                pages.append(Page(slots=[pending_portrait, slot]))
                pending_portrait = None
        else:
            flush_pending()
            pages.append(Page(slots=[slot]))

    flush_pending()
    return pages
