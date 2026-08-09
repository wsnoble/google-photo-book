from __future__ import annotations

import hashlib
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

JPEG_QUALITY = 85
# Used when no resize is applied (source is already at or below the
# target): a mandatory re-encode still happens (to apply EXIF rotation
# reliably via Pillow), but there's no size-reduction trade-off to spend
# quality against, so keep it high to minimize generation loss.
JPEG_QUALITY_NO_RESIZE = 95


def prepare_for_print(
    image_path: Path,
    cache_dir: Path,
    cell_width_px: int,
    cell_height_px: int,
) -> Path:
    """Return a path to a print-ready copy of image_path, sized for its
    actual placement (cell_width_px x cell_height_px, at 300 PPI) rather
    than a one-size-fits-all cap.

    Every photo is shown at its full frame, uncropped (object-fit: contain)
    -- cropping to fill a cell can cut off important content, so cells are
    sized to the photo's own aspect ratio instead, leaving whitespace
    rather than cropping. Resolution is capped to the long edge of the
    cell, sufficient since contain-fit never crops (resolution is bounded
    by whichever axis is the tighter fit).

    Never upsamples past the original: if the source is smaller than the
    target in a relevant dimension, it's used as-is (or merely
    re-oriented/re-encoded) since no processing can add real detail --
    that's an inherent source-resolution limit, not something this
    function can fix.

    Cached in cache_dir, keyed by the source file's identity, mtime, and
    the requested placement, so repeated builds don't redo the work for
    unchanged photos in unchanged positions.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_path = cache_dir / f"{_cache_key(image_path, cell_width_px, cell_height_px)}.jpg"
    if cached_path.is_file():
        return cached_path

    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        orig_w, orig_h = img.size

        long_edge_target = max(cell_width_px, cell_height_px)
        needed_scale = long_edge_target / max(orig_w, orig_h)
        scale = min(needed_scale, 1.0)  # never upsample

        if scale < 1.0:
            new_size = (round(orig_w * scale), round(orig_h * scale))
            img = img.resize(new_size, Image.LANCZOS)
            quality = JPEG_QUALITY
        else:
            quality = JPEG_QUALITY_NO_RESIZE

        img.convert("RGB").save(cached_path, format="JPEG", quality=quality)

    return cached_path


def prepare_cover_crop(
    image_path: Path,
    cache_dir: Path,
    panel_width_px: int,
    panel_height_px: int,
) -> Path:
    """Return a path to a print-ready copy of image_path, center-cropped
    and resized to exactly panel_width_px x panel_height_px.

    Unlike prepare_for_print (used for every interior page, which never
    crops), a book cover panel must be filled edge-to-edge with no
    whitespace -- so this is the one deliberate exception to the
    interior's uncropped-everywhere design. The crop is centered: whichever
    axis the source is proportionally wider on gets trimmed evenly from
    both sides.

    Cached in cache_dir, keyed by the source file's identity, mtime, and
    the requested panel size, matching prepare_for_print's cache scheme.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_path = cache_dir / f"cover-{_cache_key(image_path, panel_width_px, panel_height_px)}.jpg"
    if cached_path.is_file():
        return cached_path

    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        orig_w, orig_h = img.size

        target_ratio = panel_width_px / panel_height_px
        src_ratio = orig_w / orig_h
        if src_ratio > target_ratio:
            crop_w = round(orig_h * target_ratio)
            x0 = (orig_w - crop_w) // 2
            box = (x0, 0, x0 + crop_w, orig_h)
        else:
            crop_h = round(orig_w / target_ratio)
            y0 = (orig_h - crop_h) // 2
            box = (0, y0, orig_w, y0 + crop_h)
        img = img.crop(box).resize((panel_width_px, panel_height_px), Image.LANCZOS)
        img.convert("RGB").save(cached_path, format="JPEG", quality=JPEG_QUALITY)

    return cached_path


def _cache_key(image_path: Path, cell_width_px: int, cell_height_px: int) -> str:
    stat = image_path.stat()
    raw = (
        f"{image_path.resolve()}::{stat.st_mtime_ns}::{stat.st_size}"
        f"::{cell_width_px}::{cell_height_px}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
