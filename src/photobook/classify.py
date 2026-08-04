from __future__ import annotations

from typing import Literal

from photobook.model import Photo

Orientation = Literal["portrait", "landscape", "square", "panorama"]

_SQUARE_TOLERANCE = 0.05
_PANORAMA_RATIO = 2.0

# EXIF orientation values where the displayed image is rotated 90 degrees
# relative to the stored pixel dimensions.
_ROTATED_EXIF_ORIENTATIONS = {5, 6, 7, 8}


def classify_photo(photo: Photo) -> Orientation:
    """Classify a photo's displayed orientation from its dimensions.

    Accounts for EXIF orientation: a phone photo taken in portrait mode is
    often stored with width > height and an EXIF rotation flag, so the raw
    `width`/`height` don't reflect how the image actually displays.
    """
    width, height = photo.width, photo.height
    if photo.orientation in _ROTATED_EXIF_ORIENTATIONS:
        width, height = height, width

    if width <= 0 or height <= 0:
        return "landscape"

    ratio = width / height
    if ratio >= _PANORAMA_RATIO or ratio <= 1 / _PANORAMA_RATIO:
        return "panorama"
    if abs(ratio - 1) <= _SQUARE_TOLERANCE:
        return "square"
    return "landscape" if ratio > 1 else "portrait"
