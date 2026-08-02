from __future__ import annotations

from photobook.model import Photo


def order_photos(photos: list[Photo]) -> list[Photo]:
    """Order photos by their resolved timestamp.

    Photos with an unknown timestamp are appended at the end, in their
    original relative order, since there's nothing to sort them by.
    """
    dated = [photo for photo in photos if photo.timestamp is not None]
    undated = [photo for photo in photos if photo.timestamp is None]
    return sorted(dated, key=lambda photo: photo.timestamp) + undated
