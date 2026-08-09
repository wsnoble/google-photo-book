from __future__ import annotations

import math
import os
import platform
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# WeasyPrint loads pango/glib via dlopen, which on Apple Silicon Homebrew
# installs isn't on the default dynamic-library search path -- see
# render.py's identical fix for why this has to happen before importing
# weasyprint, and can't rely on render.py having done it first (this module
# can be used on its own, e.g. from cli.py's `cover` command).
if platform.system() == "Darwin":
    _existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    _brew_libs = [p for p in ("/opt/homebrew/lib", "/usr/local/lib") if os.path.isdir(p)]
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join(
        [p for p in [_existing, *_brew_libs] if p]
    )

from weasyprint import HTML  # noqa: E402

from photobook.fonts import font_template_context
from photobook.imaging import prepare_cover_crop
from photobook.model import Photo

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Blurb's Specification Calculator (https://www.blurb.com/make/pdf_to_book/
# booksize_calculator) said 1491 x 648pt for Standard Landscape, Hardcover
# ImageWrap, Standard paper, 90 pages -- but Blurb's actual PDF-uploader
# preflight rejected a cover built to that size, reporting the real
# required size as 20.889 x 8.993in (2026-08-09, live error message):
# "[Cover PDF] Page 1: Invalid dimensions, got [20.708 in x 9.000 in],
# expected [20.889 in x 8.993 in]." The calculator's number is apparently
# just wrong (or stale) for this configuration -- the live preflight is
# authoritative, so these constants are taken from that error message, not
# the calculator. Front/back panel trim width (703pt) and bleed (22pt) are
# assumed unchanged from the calculator (they're physical board/bleed
# properties that don't depend on page count -- only the spine, which is
# literally the thickness of the interior page block, does), so the whole
# ~13pt width discrepancy is attributed to the spine.
#
# Like the calculator's number before it, this is only verified for
# COVER_VERIFIED_PAGE_COUNT interior pages -- build_cover_pdf refuses to
# run for any other count rather than silently producing a wrong-width
# spine on a physical, unreturnable printed book. If the page count
# changes, re-upload a test cover and read the corrected size from the
# preflight error the same way, rather than trusting the calculator.
COVER_VERIFIED_PAGE_COUNT = 90
COVER_PAGE_WIDTH_PT = 20.889 * 72  # 1504.008
COVER_PAGE_HEIGHT_PT = 8.993 * 72  # 647.496
COVER_BLEED_PT = 22

COVER_SAFE_MARGIN_PT = 18  # inset from trim edges, per the same spec page

_PANEL_TRIM_WIDTH_PT = 703  # unchanged from the calculator -- see comment above
COVER_SPINE_TRIM_WIDTH_PT = COVER_PAGE_WIDTH_PT - 2 * COVER_BLEED_PT - 2 * _PANEL_TRIM_WIDTH_PT
# Each panel's trim width, plus the bleed on its own outer edge (there's no
# bleed against the spine -- that edge isn't trimmed).
_PANEL_WIDTH_PT = _PANEL_TRIM_WIDTH_PT + COVER_BLEED_PT  # 725, the full image area

_TARGET_PPI = 300


def build_cover_pdf(
    front_photo: Photo,
    back_photo: Photo,
    output_path: Path,
    *,
    interior_page_count: int,
    book_title: str,
    book_subtitle: str | None = None,
) -> None:
    """Render the single-spread cover PDF (back cover, spine, front cover
    left to right) for Blurb's Hardcover ImageWrap: front and back photos
    are center-cropped to fill their panel edge-to-edge (see
    imaging.prepare_cover_crop -- the one place in this codebase that
    crops a photo), the spine gets a solid background with the title read
    bottom-to-top, and the front panel gets the title/subtitle overlaid
    near the top.

    Raises ValueError if interior_page_count doesn't match
    COVER_VERIFIED_PAGE_COUNT -- see that constant's comment.
    """
    if interior_page_count != COVER_VERIFIED_PAGE_COUNT:
        raise ValueError(
            f"Cover spine width ({COVER_SPINE_TRIM_WIDTH_PT:.2f}pt) was only confirmed against "
            f"Blurb's live PDF-uploader preflight for a {COVER_VERIFIED_PAGE_COUNT}-page interior "
            f"PDF, but this book has {interior_page_count} pages. Upload a test cover at this "
            "page count, read the corrected size from the preflight error (don't trust "
            "https://www.blurb.com/make/pdf_to_book/booksize_calculator -- see the comment "
            "above these constants), then update the constants in cover.py."
        )

    cache_dir = output_path.parent / ".image_cache"
    panel_width_px = _pt_to_px(_PANEL_WIDTH_PT)
    panel_height_px = _pt_to_px(COVER_PAGE_HEIGHT_PT)

    front_uri = (
        prepare_cover_crop(front_photo.image_path, cache_dir, panel_width_px, panel_height_px)
        .resolve()
        .as_uri()
    )
    back_uri = (
        prepare_cover_crop(back_photo.image_path, cache_dir, panel_width_px, panel_height_px)
        .resolve()
        .as_uri()
    )

    front_panel_left_pt = _PANEL_WIDTH_PT + COVER_SPINE_TRIM_WIDTH_PT

    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=True)
    template = env.get_template("cover.html.jinja")
    html = template.render(
        page_width_pt=COVER_PAGE_WIDTH_PT,
        page_height_pt=COVER_PAGE_HEIGHT_PT,
        panel_width_pt=_PANEL_WIDTH_PT,
        spine_left_pt=_PANEL_WIDTH_PT,
        spine_width_pt=COVER_SPINE_TRIM_WIDTH_PT,
        front_panel_left_pt=front_panel_left_pt,
        front_title_left_pt=front_panel_left_pt + COVER_SAFE_MARGIN_PT,
        front_title_width_pt=_PANEL_TRIM_WIDTH_PT - 2 * COVER_SAFE_MARGIN_PT,
        safe_top_pt=COVER_BLEED_PT + COVER_SAFE_MARGIN_PT,
        front_image_uri=front_uri,
        back_image_uri=back_uri,
        book_title=book_title,
        front_title_lines=book_title.split("\n"),
        book_subtitle=book_subtitle,
        **font_template_context(),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(output_path)


def _pt_to_px(points: float) -> int:
    return math.ceil(points / 72 * _TARGET_PPI)
