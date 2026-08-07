from __future__ import annotations

import hashlib
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

# Long-edge pixel cap for embedded book images. Sized to comfortably cover
# the largest placement in the current layout -- a full-page solo/panorama
# photo filling the ~8.375x7.5in safe area (render.py's PAGE_WIDTH_PT/
# PAGE_HEIGHT_PT minus the safe-area insets) -- at Blurb's ~300 PPI
# guidance: 8.375in * 300 = ~2513px, 7.5in * 300 = 2250px. Grid-page cells
# are always smaller subdivisions of that same safe area, so this single
# cap is safe (never below 300 PPI) for every placement without computing
# a per-cell target.
MAX_LONG_EDGE_PX = 2600
JPEG_QUALITY = 85


def prepare_for_print(image_path: Path, cache_dir: Path) -> Path:
    """Return a path to a print-ready copy of image_path: EXIF-oriented,
    downsampled to MAX_LONG_EDGE_PX on the long edge if larger (never
    upsampled), re-encoded as JPEG. Cached in cache_dir, keyed by the
    source file's identity and mtime, so repeated builds don't redo the
    work for unchanged photos.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_path = cache_dir / f"{_cache_key(image_path)}.jpg"
    if cached_path.is_file():
        return cached_path

    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((MAX_LONG_EDGE_PX, MAX_LONG_EDGE_PX), Image.LANCZOS)
        img.convert("RGB").save(cached_path, format="JPEG", quality=JPEG_QUALITY)

    return cached_path


def _cache_key(image_path: Path) -> str:
    stat = image_path.stat()
    raw = (
        f"{image_path.resolve()}::{stat.st_mtime_ns}::{stat.st_size}"
        f"::{MAX_LONG_EDGE_PX}::{JPEG_QUALITY}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
