from __future__ import annotations

import csv
from pathlib import Path

from photobook.chapters import assign_countries, group_into_chapters, take_divider_photos
from photobook.layout import Page, build_pages
from photobook.model import Photo
from photobook.ordering import order_photos

_COLUMNS = ["row_type", "image_path", "filename", "date", "tag", "chapter_title", "solo"]


def export_review_file(photos: list[Photo], path: Path) -> None:
    """Generate a review.tsv (see review.py for the format `build
    --review-file` reads back) from freshly-imported photos:

    - Order: by timestamp, undated photos grouped at the end (same rule
      as ordering.order_photos with no manual_order) -- a reasonable
      starting point to hand-edit, not a recovered fact.
    - Chapters: auto-assigned by country from GPS data (see chapters.py),
      inserted as divider rows.
    - Captions: an existing real caption is carried over as-is into the
      tag column; a photo with no caption is left blank rather than
      guessed at here -- filling in a short descriptive tag for those
      (parenthesized, so it's recognizable as a reference note rather
      than a real caption -- see review.py) requires actually looking at
      each photo, which this function has no way to do on its own.
    - solo column: prefilled "true" for every photo that the current
      order/chapters would put alone on a page (mirroring
      render.py's chapter-divider-then-build_pages composition exactly,
      including the leftover-merge behavior in layout.py), so you only
      need to flip the ones you disagree with rather than starting blank.
    """
    ordered = order_photos(photos)
    countries = assign_countries(ordered)
    groups = group_into_chapters(ordered, countries)
    solo_image_paths = _compute_solo_image_paths(groups)

    rows: list[dict] = []
    last_chapter_title: str | None = None
    for country, group_photos in groups:
        if country is not None and country != last_chapter_title:
            rows.append({"row_type": "chapter", "chapter_title": country})
            last_chapter_title = country
        for photo in group_photos:
            rows.append(_photo_row(photo, solo_image_paths))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def _photo_row(photo: Photo, solo_image_paths: set[str]) -> dict:
    return {
        "row_type": "photo",
        "image_path": str(photo.image_path),
        "filename": photo.image_path.name,
        "date": photo.timestamp.strftime("%Y-%m-%d") if photo.timestamp else "",
        "tag": photo.caption or "",
        "chapter_title": "",
        "solo": "true" if str(photo.image_path) in solo_image_paths else "",
    }


def _compute_solo_image_paths(groups: list[tuple[str | None, list[Photo]]]) -> set[str]:
    """Every photo that the current order/chapters would put alone on a
    page, right now -- mirrors render.py's _groups_to_page_data exactly
    (divider takes up to CHAPTER_DIVIDER_PHOTO_COUNT photos first, the
    rest goes through build_pages), without doing any image processing.
    """
    solo_image_paths: set[str] = set()
    last_chapter_title: str | None = None
    for country, group_photos in groups:
        if country is not None and country != last_chapter_title:
            _divider_photos, group_photos = take_divider_photos(group_photos)
            last_chapter_title = country
        for page in build_pages(group_photos):
            _add_if_solo(page, solo_image_paths)
    return solo_image_paths


def _add_if_solo(page: Page, solo_image_paths: set[str]) -> None:
    if len(page.slots) == 1:
        solo_image_paths.add(str(page.slots[0].photo.image_path))
