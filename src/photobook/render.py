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

from photobook.imaging import FitMode, prepare_for_print
from photobook.layout import Page, build_pages
from photobook.model import Photo
from photobook.ordering import order_photos

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


def build_book_pdf(
    photos: list[Photo],
    output_path: Path,
    *,
    book_title: str = "Photo Book",
    manual_order: list[str] | None = None,
    guess_leftover_positions: bool = False,
) -> None:
    """Render the actual photo book: panoramas get their own full-frame
    page; everything else is grouped into grid pages (mostly 4-5 photos,
    occasionally 2, cropped to fill uniform cells), captions below each
    photo when present with no reserved space when absent. Each photo is
    downsampled for its actual placement (see imaging.prepare_for_print)
    before embedding, cached under output_path.parent/.image_cache.
    """
    ordered = order_photos(
        photos, manual_order=manual_order, guess_leftover_positions=guess_leftover_positions
    )
    pages = build_pages(ordered)

    cache_dir = output_path.parent / ".image_cache"
    page_data = [_page_to_template_data(page, cache_dir) for page in pages]

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
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(output_path)


def _page_to_template_data(page: Page, cache_dir: Path) -> dict:
    if sum(page.rows) != len(page.slots):
        raise ValueError(
            f"Page.rows {page.rows} (sum={sum(page.rows)}) doesn't match "
            f"its slot count ({len(page.slots)}) -- would silently drop photos."
        )

    is_grid = len(page.slots) > 1
    fit: FitMode = "cover" if is_grid else "contain"
    # Rows split the content height equally regardless of column count
    # (matches the CSS: each .row has flex: 1 within a flex-column .page).
    row_height_px = _pt_to_px(_CONTENT_HEIGHT_PT / len(page.rows))

    rows: list[list[dict]] = []
    slot_index = 0
    for row_size in page.rows:
        # Columns within a row split the content width equally (each
        # .cell has flex: 1 within a flex-row .row).
        cell_width_px = _pt_to_px(_CONTENT_WIDTH_PT / row_size)
        row_slots = page.slots[slot_index : slot_index + row_size]
        rows.append(
            [
                {
                    "image_uri": prepare_for_print(
                        slot.photo.image_path, cache_dir, cell_width_px, row_height_px, fit
                    )
                    .resolve()
                    .as_uri(),
                    "caption": slot.photo.caption,
                }
                for slot in row_slots
            ]
        )
        slot_index += row_size

    return {"rows": rows, "is_grid": is_grid}


def _pt_to_px(points: float) -> int:
    return round(points / 72 * _TARGET_PPI * _RESOLUTION_HEADROOM)
