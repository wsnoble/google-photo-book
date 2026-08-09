from __future__ import annotations

import os
import platform
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# WeasyPrint loads pango/glib via dlopen, which on Apple Silicon Homebrew
# installs isn't on the default dynamic-library search path. Fix this before
# importing weasyprint so `photobook build` works without shell setup.
if platform.system() == "Darwin":
    _existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    _brew_libs = [p for p in ("/opt/homebrew/lib", "/usr/local/lib") if os.path.isdir(p)]
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join(
        [p for p in [_existing, *_brew_libs] if p]
    )

from weasyprint import HTML  # noqa: E402

from photobook.chapters import assign_countries, group_into_chapters, take_divider_photos
from photobook.classify import classify_photo, effective_dimensions
from photobook.fonts import font_template_context
from photobook.imaging import prepare_for_print
from photobook.layout import Page, build_pages
from photobook.model import Photo
from photobook.ordering import order_photos
from photobook.review import load_review_file

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Verified 2026-08-06 against Blurb's Specification Calculator
# (https://www.blurb.com/make/pdf_to_book/booksize_calculator) for
# Standard Landscape, Hardcover ImageWrap, Standard paper -- identical
# across page counts tested (20 and 92), so only the cover spine varies
# with page count, not this interior page geometry. All in points (pt),
# matching Blurb's own units. Note the real trim is 9.5x8in, not the
# "10x8" the size is marketed as.
PAGE_WIDTH_PT = 693  # exported PDF page size (trim + bleed)
PAGE_HEIGHT_PT = 594
_TRIM_WIDTH_PT = 684  # for reference; not needed for layout directly
_TRIM_HEIGHT_PT = 576
BLEED_PT = 9  # top, bottom, and outside edge only -- not the binding edge
SAFE_MARGIN_OUTER_PT = 18  # top, bottom, outside edge
SAFE_MARGIN_BINDING_PT = 36  # binding (gutter) edge only, double the others

# The binding-edge margin (36pt) applies to only one side -- left or
# right, depending on whether a page is recto/verso -- which this
# layout doesn't track (no left/right-hand-page concept). Applying the
# larger binding margin, and bleed, conservatively on BOTH left and
# right is always safe (never places content where trimming could cut
# it) at the cost of some usable width versus the exact per-side spec.
_SAFE_AREA_TOP_BOTTOM_PT = BLEED_PT + SAFE_MARGIN_OUTER_PT  # 27
_SAFE_AREA_LEFT_RIGHT_PT = BLEED_PT + SAFE_MARGIN_BINDING_PT  # 45

# The actual content area available for photos, after the safe-area inset.
_CONTENT_WIDTH_PT = PAGE_WIDTH_PT - 2 * _SAFE_AREA_LEFT_RIGHT_PT  # 603
_CONTENT_HEIGHT_PT = PAGE_HEIGHT_PT - 2 * _SAFE_AREA_TOP_BOTTOM_PT  # 540

_TARGET_PPI = 300
# Cells are sized to the full row/column split of the content area, not
# accounting for each cell's own padding or caption (which further shrink
# the actual displayed image below the cell size) -- so sizing to the
# full cell is already a conservative overestimate. This adds a little
# more headroom on top of that for rounding, rather than sizing images to
# the exact geometric minimum.
_RESOLUTION_HEADROOM = 1.15

# Matches book.html.jinja's `.cell { padding: 0.15in; }` /
# `.page.solo .cell { padding: 0.3in; }`.
_GRID_CELL_PADDING_PT = 0.15 * 72
_SOLO_CELL_PADDING_PT = 0.3 * 72

# Matches book.html.jinja's `.page.grid .caption` / `.page.solo .caption`
# font-size and margin-top. `.caption` doesn't set an explicit line-height,
# so this estimates the UA/font default rather than reading a real value --
# deliberately on the generous side, since underestimating is what causes
# the actual overflow bug this is meant to prevent.
_GRID_CAPTION_FONT_SIZE_PT = 7
_GRID_CAPTION_MARGIN_TOP_PT = 0.05 * 72
_SOLO_CAPTION_FONT_SIZE_PT = 11
_SOLO_CAPTION_MARGIN_TOP_PT = 0.15 * 72
_CAPTION_LINE_HEIGHT_FACTOR = 1.35
# Rough average character width for a serif font, as a fraction of its
# font-size -- only used to estimate how many lines a caption wraps to,
# so it doesn't need to be exact, just not an underestimate.
_AVG_CHAR_WIDTH_FACTOR = 0.5
_MAX_CAPTION_LINES = 4


def build_book_pdf(
    photos: list[Photo],
    output_path: Path,
    *,
    book_title: str = "Photo Book",
    book_subtitle: str | None = None,
    manual_order: list[str] | None = None,
    guess_leftover_positions: bool = False,
    chapters: bool = False,
    review_file: Path | None = None,
) -> int:
    """Render the actual photo book: a title page comes first, then
    panoramas get their own full-frame page; everything else is grouped
    into grid pages (mostly 4-5 photos, occasionally 2). Every photo is
    shown at its full frame, uncropped -- cells are sized to each photo's
    own aspect ratio rather than cropping to fill a uniform shape, so a
    photo's own dimensions decide how much of the cell it actually fills,
    leaving whitespace rather than cutting off content. Captions sit
    directly below each photo when present, with no reserved space when
    absent. Each photo is downsampled for its actual placement (see
    imaging.prepare_for_print) before embedding, cached under
    output_path.parent/.image_cache.

    With chapters=True, photos are grouped into country chapters (see
    chapters.py) with a divider page between them, and each chapter's grid
    pages restart the page-size pattern fresh rather than continuing it
    across the whole book.

    review_file takes full precedence over manual_order,
    guess_leftover_positions, and chapters: it supplies its own order,
    chapter boundaries, and caption overrides (see review.py), so those are
    ignored when it's given. It can also exclude photos (an image_path not
    listed is dropped, not appended), so the caller can't assume every
    input photo made it into the book -- returns the number that actually
    did.
    """
    cache_dir = output_path.parent / ".image_cache"
    if review_file is not None:
        groups = load_review_file(review_file, photos)
        page_data = _groups_to_page_data(groups, cache_dir)
        included_count = sum(len(group_photos) for _, group_photos in groups)
    else:
        ordered = order_photos(
            photos, manual_order=manual_order, guess_leftover_positions=guess_leftover_positions
        )
        included_count = len(ordered)
        if chapters:
            countries = assign_countries(ordered)
            groups = group_into_chapters(ordered, countries)
            page_data = _groups_to_page_data(groups, cache_dir)
        else:
            page_data = [
                {"kind": "photos", **_page_to_template_data(page, cache_dir)}
                for page in build_pages(ordered)
            ]
    # A literal "\n" in book_title (e.g. from a config.yaml double-quoted
    # string) is a deliberate manual line break, not raw HTML -- split it
    # into separate lines here rather than templating it in unescaped.
    title_page = {
        "kind": "title",
        "title_lines": book_title.split("\n"),
        "subtitle": book_subtitle,
    }
    page_data = [title_page, *page_data]

    # `select_autoescape` matches on filename suffix (e.g. ".html"), which
    # our "*.html.jinja" template names never match -- autoescape=True
    # unconditionally is what we actually want, since every template here
    # renders HTML.
    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=True)
    template = env.get_template("book.html.jinja")
    html = template.render(
        pages=page_data,
        book_title=book_title,
        page_width_pt=PAGE_WIDTH_PT,
        page_height_pt=PAGE_HEIGHT_PT,
        safe_area_top_bottom_pt=_SAFE_AREA_TOP_BOTTOM_PT,
        safe_area_left_right_pt=_SAFE_AREA_LEFT_RIGHT_PT,
        **font_template_context(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(output_path)
    return included_count


def _groups_to_page_data(
    groups: list[tuple[str | None, list[Photo]]], cache_dir: Path
) -> list[dict]:
    page_data: list[dict] = []
    last_chapter_title: str | None = None
    for country, group_photos in groups:
        # Skip the divider if this group's country matches the last one we
        # actually rendered a divider for, even across an intervening
        # None-labeled group (e.g. Italy, Italy, None, Italy must render one
        # "Italy" divider, not two) -- the groups list only groups
        # *adjacent* equal labels, so that dedup has to happen here.
        if country is not None and country != last_chapter_title:
            divider_photos, group_photos = take_divider_photos(group_photos)
            page_data.append(_chapter_page_data(country, divider_photos, cache_dir))
            last_chapter_title = country
        for page in build_pages(group_photos):
            page_data.append({"kind": "photos", **_page_to_template_data(page, cache_dir)})
    return page_data


def _chapter_page_data(title: str, divider_photos: list[Photo], cache_dir: Path) -> dict:
    """A chapter divider page: title occupies the top-left quarter.

    Up to chapters.CHAPTER_DIVIDER_PHOTO_COUNT more photos fill the rest
    of a 2x2 grid (any quadrant beyond what's available stays blank)
    rather than the title alone taking a full page -- *unless* one of
    them is a panorama (chapters.take_divider_photos never selects more
    than one), in which case it spans the full-width bottom row instead
    of a single quadrant -- a quarter of the page is too small a fraction
    to show one properly -- leaving at most one ordinary photo to share
    the top row with the title.
    """
    quarter_width_pt = _CONTENT_WIDTH_PT / 2
    quarter_height_pt = _CONTENT_HEIGHT_PT / 2

    panorama = next((p for p in divider_photos if classify_photo(p) == "panorama"), None)
    other_photos = [p for p in divider_photos if p is not panorama]

    top_photo = (
        _photo_cell_data(other_photos[0], cache_dir, quarter_width_pt, quarter_height_pt)
        if other_photos
        else None
    )

    if panorama is not None:
        return {
            "kind": "chapter",
            "title": title,
            "top_photo": top_photo,
            "panorama": _photo_cell_data(panorama, cache_dir, _CONTENT_WIDTH_PT, quarter_height_pt),
            "bottom_photos": [],
        }

    return {
        "kind": "chapter",
        "title": title,
        "top_photo": top_photo,
        "panorama": None,
        "bottom_photos": [
            _photo_cell_data(photo, cache_dir, quarter_width_pt, quarter_height_pt)
            for photo in other_photos[1:3]
        ],
    }


def _photo_cell_data(
    photo: Photo, cache_dir: Path, cell_width_pt: float, cell_height_pt: float
) -> dict:
    """image_uri + image_max_{width,height}_pt for one photo shown at
    cell_width_pt x cell_height_pt (grid-style padding/caption sizing --
    used for every multi-photo-per-page cell, chapter divider quadrants
    included; solo/panorama-alone pages size directly in
    _page_to_template_data instead, with their own larger padding).
    """
    cell_width_px = _pt_to_px(cell_width_pt)
    cell_height_px = _pt_to_px(cell_height_pt)
    available_width_pt = cell_width_pt - 2 * _GRID_CELL_PADDING_PT
    return {
        "image_uri": prepare_for_print(photo.image_path, cache_dir, cell_width_px, cell_height_px)
        .resolve()
        .as_uri(),
        "caption": photo.caption,
        **_image_box_pt(
            photo,
            available_width_pt,
            cell_height_pt
            - 2 * _GRID_CELL_PADDING_PT
            - _caption_reservation_pt(photo.caption, available_width_pt, is_grid=True),
        ),
    }


def _page_to_template_data(page: Page, cache_dir: Path) -> dict:
    if sum(page.rows) != len(page.slots):
        raise ValueError(
            f"Page.rows {page.rows} (sum={sum(page.rows)}) doesn't match "
            f"its slot count ({len(page.slots)}) -- would silently drop photos."
        )

    is_grid = len(page.slots) > 1
    padding_pt = _GRID_CELL_PADDING_PT if is_grid else _SOLO_CELL_PADDING_PT
    # Rows split the content height equally regardless of column count
    # (matches the CSS: each .row has flex: 1 within a flex-column .page).
    row_height_pt = _CONTENT_HEIGHT_PT / len(page.rows)
    row_height_px = _pt_to_px(row_height_pt)

    rows: list[list[dict]] = []
    slot_index = 0
    for row_size in page.rows:
        # Columns within a row split the content width equally (each
        # .cell has flex: 1 within a flex-row .row).
        cell_width_pt = _CONTENT_WIDTH_PT / row_size
        cell_width_px = _pt_to_px(cell_width_pt)
        available_width_pt = cell_width_pt - 2 * padding_pt
        row_slots = page.slots[slot_index : slot_index + row_size]
        slot_dicts = []
        for slot in row_slots:
            slot_dicts.append(
                {
                    "image_uri": prepare_for_print(
                        slot.photo.image_path, cache_dir, cell_width_px, row_height_px
                    )
                    .resolve()
                    .as_uri(),
                    "caption": slot.photo.caption,
                    **_image_box_pt(
                        slot.photo,
                        available_width_pt,
                        row_height_pt
                        - 2 * padding_pt
                        - _caption_reservation_pt(
                            slot.photo.caption, available_width_pt, is_grid=is_grid
                        ),
                    ),
                }
            )
        rows.append(slot_dicts)
        slot_index += row_size

    return {"rows": rows, "is_grid": is_grid}


def _image_box_pt(photo: Photo, available_width_pt: float, available_height_pt: float) -> dict:
    """Exact rendered width/height (in pt) of a photo under object-fit:
    contain within its cell, computed here rather than left to CSS.

    A contain-fit image is usually smaller than its cell in one dimension
    (e.g. a wide panorama in a roughly-square cell has empty space above
    and below it) -- if the caption just follows a box sized to the full
    cell, it ends up far below the actual photo, in that empty space,
    rather than snug against it. Computing the real rendered size here
    lets the template give the image an explicit (not percentage)
    width/height, so its wrapper shrink-wraps to the photo's actual
    displayed size and the caption sits directly beneath it, with the
    whole (photo + caption) block then centered as a unit in the cell.
    Percentage-based sizing can't do this: the wrapper would need a
    definite height to size the image against, but making it definite
    (e.g. height: 100%) is exactly what recreates the oversized-box
    problem this avoids.
    """
    # A caption reservation subtracted by the caller could, for a
    # pathologically long caption in a tiny cell, leave zero or negative
    # height. Floor it so the image never inverts/disappears -- worst case
    # the caption overlaps it slightly, rather than the geometry breaking
    # outright.
    available_width_pt = max(available_width_pt, 1.0)
    available_height_pt = max(available_height_pt, 1.0)

    width, height = effective_dimensions(photo)
    if width <= 0 or height <= 0:
        return {
            "image_max_width_pt": available_width_pt,
            "image_max_height_pt": available_height_pt,
        }

    scale = min(available_width_pt / width, available_height_pt / height)
    return {
        "image_max_width_pt": width * scale,
        "image_max_height_pt": height * scale,
    }


def _caption_reservation_pt(caption: str | None, cell_width_pt: float, *, is_grid: bool) -> float:
    """How much height (pt) to reserve below a photo for its caption, so
    the image is sized to leave room for it instead of the two together
    overflowing the cell (the image box was previously sized to the full
    cell regardless of whether a caption would also need to fit under it).
    0 when there's no caption.

    Estimates how many lines the caption will wrap to from its length and
    the cell's width, since the real answer depends on WeasyPrint's actual
    text shaping, which isn't available here -- deliberately conservative
    (see the module-level caption constants' comment), capped at
    _MAX_CAPTION_LINES so one pathologically long caption can't shrink the
    image to nothing.
    """
    if not caption:
        return 0.0

    font_size_pt = _GRID_CAPTION_FONT_SIZE_PT if is_grid else _SOLO_CAPTION_FONT_SIZE_PT
    margin_top_pt = _GRID_CAPTION_MARGIN_TOP_PT if is_grid else _SOLO_CAPTION_MARGIN_TOP_PT

    avg_char_width_pt = font_size_pt * _AVG_CHAR_WIDTH_FACTOR
    chars_per_line = max(1, int(cell_width_pt / avg_char_width_pt))
    estimated_lines = min(_MAX_CAPTION_LINES, -(-len(caption) // chars_per_line))  # ceil div

    line_height_pt = font_size_pt * _CAPTION_LINE_HEIGHT_FACTOR
    return margin_top_pt + estimated_lines * line_height_pt


def _pt_to_px(points: float) -> int:
    return round(points / 72 * _TARGET_PPI * _RESOLUTION_HEADROOM)
