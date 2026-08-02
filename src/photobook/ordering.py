from __future__ import annotations

from bisect import bisect_left

from photobook.model import Photo


def order_photos(photos: list[Photo], manual_order: list[str] | None = None) -> list[Photo]:
    """Order photos for the book.

    Without `manual_order`, sorts by resolved timestamp; photos with an
    unknown timestamp are appended at the end, in their original relative
    order, since there's nothing to sort them by.

    With `manual_order` (a list of `image_path` strings, e.g. recovered
    from the source album's actual display order), photos matching an
    entry keep that order. Photos not in `manual_order` are interpolated
    by timestamp among the matched photos' timestamps, so a handful of
    missing entries don't get dumped out of context at the end; photos
    with neither a manual-order entry nor a timestamp go last.
    """
    if manual_order is not None:
        return _order_with_manual_override(photos, manual_order)

    dated = [photo for photo in photos if photo.timestamp is not None]
    undated = [photo for photo in photos if photo.timestamp is None]
    return sorted(dated, key=lambda photo: photo.timestamp) + undated


def _order_with_manual_override(photos: list[Photo], manual_order: list[str]) -> list[Photo]:
    by_path = {str(photo.image_path): photo for photo in photos}
    matched_paths = [path for path in manual_order if path in by_path]
    matched = [by_path[path] for path in matched_paths]
    leftover = [photo for photo in photos if str(photo.image_path) not in set(matched_paths)]

    dated_leftover = sorted(
        (photo for photo in leftover if photo.timestamp is not None),
        key=lambda photo: photo.timestamp,
    )
    undated_leftover = [photo for photo in leftover if photo.timestamp is None]

    result = list(matched)
    timestamps = [photo.timestamp for photo in matched]
    for photo in dated_leftover:
        index = bisect_left(timestamps, photo.timestamp)
        result.insert(index, photo)
        timestamps.insert(index, photo.timestamp)

    result.extend(undated_leftover)
    return result
