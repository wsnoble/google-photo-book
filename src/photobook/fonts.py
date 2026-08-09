from __future__ import annotations

from pathlib import Path

_FONTS_DIR = Path(__file__).parent / "templates" / "fonts"


def font_template_context() -> dict[str, str]:
    """file:// URIs for the bundled EB Garamond font files, for the
    @font-face src in _fonts.html.jinja. WeasyPrint resolves url() the same
    way it resolves <img src>: needs an absolute/file:// URI, not a path
    relative to the HTML string it's rendering (which has no base to
    resolve against), matching how render.py already handles image_uri.
    """
    return {
        "garamond_regular_uri": (_FONTS_DIR / "EBGaramond[wght].ttf").resolve().as_uri(),
        "garamond_italic_uri": (_FONTS_DIR / "EBGaramond-Italic[wght].ttf").resolve().as_uri(),
    }
