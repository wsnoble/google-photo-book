from __future__ import annotations

from datetime import datetime

from photobook.model import Photo


def order_photos(
    photos: list[Photo],
    manual_order: list[str] | None = None,
    guess_leftover_positions: bool = False,
) -> list[Photo]:
    """Order photos for the book.

    Without `manual_order`, sorts by resolved timestamp; photos with an
    unknown timestamp are appended at the end, in their original relative
    order, since there's nothing to sort them by.

    With `manual_order` (a list of `image_path` strings, e.g. recovered
    from the source album's actual display order), photos matching an
    entry keep that order. Photos not in `manual_order` ("leftovers") are
    handled one of two ways:

    - `guess_leftover_positions=False` (default): appended at the end —
      dated ones sorted by timestamp among themselves, undated ones last
      of all. An honest "position unknown."
    - `guess_leftover_positions=True`: each dated leftover is inserted
      next to whichever already-placed photo is chronologically closest
      (before it if earlier, after if later). This is a best-effort
      guess, not a recovered fact: a manually-curated album order is not
      chronologically local (a photo can sit next to ones taken months
      apart), so this can place a photo confidently in the wrong spot.
      Verified in practice on a real album — worth a visual check of the
      proof PDF rather than trusting it blindly. Undated leftovers still
      go last, since there's nothing to guess from.
    """
    if manual_order is not None:
        return _order_with_manual_override(photos, manual_order, guess_leftover_positions)

    dated = [photo for photo in photos if photo.timestamp is not None]
    undated = [photo for photo in photos if photo.timestamp is None]
    return sorted(dated, key=lambda photo: photo.timestamp) + undated


def _order_with_manual_override(
    photos: list[Photo], manual_order: list[str], guess_leftover_positions: bool
) -> list[Photo]:
    by_path = {str(photo.image_path): photo for photo in photos}
    matched_paths = [path for path in manual_order if path in by_path]
    matched = [by_path[path] for path in matched_paths]
    matched_set = set(matched_paths)
    leftover = [photo for photo in photos if str(photo.image_path) not in matched_set]

    dated_leftover = sorted(
        (photo for photo in leftover if photo.timestamp is not None),
        key=lambda photo: photo.timestamp,
    )
    undated_leftover = [photo for photo in leftover if photo.timestamp is None]

    if guess_leftover_positions:
        result = list(matched)
        for photo in dated_leftover:
            result.insert(_nearest_neighbor_index(result, photo.timestamp), photo)
        result.extend(undated_leftover)
        return result

    return matched + dated_leftover + undated_leftover


def _nearest_neighbor_index(result: list[Photo], timestamp: datetime) -> int:
    """Find where to insert a photo by timestamp into `result`, which is in
    manually-specified album order and so is *not* necessarily sorted by
    timestamp — a binary search over it would be invalid. Instead, insert
    immediately next to whichever already-placed photo is chronologically
    closest: before it if this photo is earlier, after if later.
    """
    best_index = len(result)
    best_diff: float | None = None
    for index, other in enumerate(result):
        if other.timestamp is None:
            continue
        diff = abs((other.timestamp - timestamp).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_index = index if timestamp < other.timestamp else index + 1
    return best_index
