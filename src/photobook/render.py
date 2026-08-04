from __future__ import annotations

import os
import platform
from pathlib import Path

import pillow_heif
from jinja2 import Environment, FileSystemLoader, select_autoescape

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

from photobook.layout import build_pages
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
    """Render the actual photo book: landscape/panorama/square photos one
    per page, portraits paired two-per-page, captions below photos when
    present with no reserved space when absent.
    """
    ordered = order_photos(
        photos, manual_order=manual_order, guess_leftover_positions=guess_leftover_positions
    )
    pages = build_pages(ordered)

    page_data = [
        {
            "slots": [
                {
                    "image_uri": slot.photo.image_path.resolve().as_uri(),
                    "caption": slot.photo.caption,
                }
                for slot in page.slots
            ]
        }
        for page in pages
    ]

    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("book.html.jinja")
    html = template.render(
        pages=page_data,
        book_title=book_title,
        page_width=PAGE_WIDTH,
        page_height=PAGE_HEIGHT,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(output_path)
