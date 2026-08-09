"""Import this module (for its side effect) before importing weasyprint.

WeasyPrint loads pango/glib via dlopen, which on Apple Silicon Homebrew
installations isn't on the default dynamic-library search path. Patching
DYLD_FALLBACK_LIBRARY_PATH here, before weasyprint is imported anywhere,
is what lets `photobook build`/`proof`/`cover` work without manual shell
setup.
"""

from __future__ import annotations

import os
import platform

if platform.system() == "Darwin":
    _existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    _brew_libs = [p for p in ("/opt/homebrew/lib", "/usr/local/lib") if os.path.isdir(p)]
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join(
        [p for p in [_existing, *_brew_libs] if p]
    )
