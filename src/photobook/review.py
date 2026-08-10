from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

from photobook.model import Photo

_REQUIRED_COLUMNS = {"row_type", "image_path", "tag", "chapter_title"}


class ReviewFileError(ValueError):
    """Raised when a review file is malformed or references an unknown photo."""


def load_review_file(path: Path, photos: list[Photo]) -> list[tuple[str | None, list[Photo]]]:
    """Parse a review TSV (as exported for manual correction) into chapter
    groups, in the file's row order.

    The file is authoritative for both order and membership: a photo not
    listed is excluded from the book -- a deliberate removal, not an
    unknown-position "leftover" the way --manual-order treats omissions.
    Chapter assignment comes from a photo row's position relative to
    "chapter" divider rows, not a per-photo field -- moving, adding, or
    deleting a divider row is how a chapter boundary is corrected.

    A photo row's `tag` column becomes that photo's caption, replacing
    whatever caption (if any) it had before -- unless it's blank or
    parenthesized (parenthesized tags are auto-generated reference
    descriptions for identifying the photo, not real captions), in which
    case the photo ends up with no caption. There's no way to say "leave
    the existing caption alone" -- the review file is authoritative for
    every column it has, matching how it's already authoritative for
    order and membership.

    An optional `solo` column ("true"/"false"/blank) overrides whether a
    photo is ever alone on a page (see layout.build_pages): "true" forces
    it onto its own page, "false" forces it to always share a page, blank
    applies the automatic panorama-based decision -- explicitly, not just
    left alone, so a blank cell can't leave a stale override in place. The
    column being absent entirely (files written before it existed) also
    leaves every photo's force_solo untouched at the Photo's own default.
    """
    by_path = {str(photo.image_path): photo for photo in photos}

    groups: list[tuple[str | None, list[Photo]]] = []
    current_chapter: str | None = None
    current_group: list[Photo] = []

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = set(reader.fieldnames or [])
        missing_columns = _REQUIRED_COLUMNS - fieldnames
        if missing_columns:
            raise ReviewFileError(
                f"{path}: missing required column(s): {', '.join(sorted(missing_columns))}"
            )
        has_solo_column = "solo" in fieldnames

        for line_number, row in enumerate(reader, start=2):
            row_type = (row.get("row_type") or "").strip()
            if row_type == "chapter":
                if current_group:
                    groups.append((current_chapter, current_group))
                    current_group = []
                current_chapter = (row.get("chapter_title") or "").strip() or None
            elif row_type == "photo":
                image_path = (row.get("image_path") or "").strip()
                photo = by_path.get(image_path)
                if photo is None:
                    raise ReviewFileError(
                        f"{path}:{line_number}: unknown image_path {image_path!r} -- "
                        "doesn't match any photo in photos.json."
                    )
                tag = (row.get("tag") or "").strip()
                is_real_caption = tag and not (tag.startswith("(") and tag.endswith(")"))
                updates: dict = {"caption": tag if is_real_caption else None}
                if has_solo_column:
                    updates["force_solo"] = _parse_solo(row.get("solo") or "", path, line_number)
                photo = replace(photo, **updates)
                current_group.append(photo)
            else:
                raise ReviewFileError(
                    f"{path}:{line_number}: row_type must be 'chapter' or 'photo', "
                    f"got {row_type!r}."
                )

    if current_group:
        groups.append((current_chapter, current_group))

    return groups


def _parse_solo(value: str, path: Path, line_number: int) -> bool | None:
    value = value.strip().lower()
    if value == "":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    raise ReviewFileError(
        f"{path}:{line_number}: solo column must be 'true', 'false', or blank, got {value!r}."
    )
