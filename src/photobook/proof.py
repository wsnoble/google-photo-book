from __future__ import annotations

import base64
import os
import platform
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pillow_heif
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageOps

# WeasyPrint loads pango/glib via dlopen, which on Apple Silicon Homebrew
# installs isn't on the default dynamic-library search path. Fix this before
# importing weasyprint so `photobook proof` works without shell setup.
if platform.system() == "Darwin":
    _existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    _brew_libs = [p for p in ("/opt/homebrew/lib", "/usr/local/lib") if os.path.isdir(p)]
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join(
        [p for p in [_existing, *_brew_libs] if p]
    )

from weasyprint import HTML  # noqa: E402

from photobook.model import Photo
from photobook.ordering import order_photos

pillow_heif.register_heif_opener()

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_THUMBNAIL_MAX_SIZE = 400
_THUMBNAIL_JPEG_QUALITY = 60


def build_proof_pdf(photos: list[Photo], output_path: Path) -> None:
    """Render a compact PDF listing every photo, in book order, with its
    filename, date, caption, and any warnings, for verifying the import
    before building the real layout.
    """
    ordered = order_photos(photos)
    entries = [
        {
            "index": index,
            "thumbnail_data_uri": _thumbnail_data_uri(photo.image_path),
            "filename": photo.image_path.name,
            "date": photo.timestamp.strftime("%Y-%m-%d") if photo.timestamp else "Unknown date",
            "caption": photo.caption,
            "warnings": photo.warnings,
        }
        for index, photo in enumerate(ordered, start=1)
    ]

    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("proof.html.jinja")
    html = template.render(
        entries=entries,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(output_path)


def _thumbnail_data_uri(image_path: Path) -> str:
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((_THUMBNAIL_MAX_SIZE, _THUMBNAIL_MAX_SIZE))
        buffer = BytesIO()
        img.convert("RGB").save(buffer, format="JPEG", quality=_THUMBNAIL_JPEG_QUALITY)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
