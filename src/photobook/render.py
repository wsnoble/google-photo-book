from __future__ import annotations

import os
import platform
from pathlib import Path

import pillow_heif
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

from photobook.layout import Page, build_pages
from photobook.model import Photo
from photobook.ordering import order_photos

pillow_heif.register_heif_opener()

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Provisional: 10x8in landscape with no bleed/margin, matching Blurb's
# "Standard Landscape 10x8" naming. Not yet reconciled against Blurb's
# Specification Calculator (page size, bleed, and safety margin per
# size/paper/cover combination) -- that's Milestone 4.
PAGE_WIDTH = "10in"
PAGE_HEIGHT = "8in"


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
    photo when present with no reserved space when absent.
    """
    ordered = order_photos(
        photos, manual_order=manual_order, guess_leftover_positions=guess_leftover_positions
    )
    pages = build_pages(ordered)

    page_data = [_page_to_template_data(page) for page in pages]

    # `select_autoescape` matches on filename suffix (e.g. ".html"), which
    # our "*.html.jinja" template names never match -- autoescape=True
    # unconditionally is what we actually want, since every template here
    # renders HTML.
    env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=True)
    template = env.get_template("book.html.jinja")
    html = template.render(
        pages=page_data,
        book_title=book_title,
        page_width=PAGE_WIDTH,
        page_height=PAGE_HEIGHT,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(output_path)


def _page_to_template_data(page: Page) -> dict:
    if sum(page.rows) != len(page.slots):
        raise ValueError(
            f"Page.rows {page.rows} (sum={sum(page.rows)}) doesn't match "
            f"its slot count ({len(page.slots)}) -- would silently drop photos."
        )

    slot_dicts = [
        {"image_uri": slot.photo.image_path.resolve().as_uri(), "caption": slot.photo.caption}
        for slot in page.slots
    ]
    rows = []
    index = 0
    for row_size in page.rows:
        rows.append(slot_dicts[index : index + row_size])
        index += row_size
    return {"rows": rows, "is_grid": len(page.slots) > 1}
