from __future__ import annotations

import itertools
from datetime import datetime

from photobook.classify import classify_photo
from photobook.model import Photo


def assign_countries(photos: list[Photo]) -> list[str | None]:
    """One country label per photo, aligned 1:1 with `photos`' order.

    Photos with GPS data are reverse-geocoded (offline, point-based nearest-
    city lookup -- not polygon/border-aware, so a coordinate very close to a
    national border can occasionally resolve to the wrong country). Photos
    without GPS inherit the country of their chronologically-nearest
    geotagged photo (by absolute timestamp delta) if they have a timestamp;
    the donor pool is the fixed set of geotagged photos only, so inheritance
    can't chain through an already-inherited photo and drift further in time
    than any single step would justify. There's no cap on how far in time an
    inheritance can reach -- a GPS-less photo far from any geotagged one
    still confidently inherits *something*, the same "best-effort guess,
    verify visually" trade-off `ordering.guess_leftover_positions` already
    makes. A photo with neither GPS nor a timestamp gets None.

    Importing reverse_geocode builds its k-d tree eagerly (~10s), so it's
    imported lazily here rather than at module load, matching cli.py's
    lazy-import pattern for WeasyPrint.
    """
    geotagged = [p for p in photos if p.latitude is not None and p.longitude is not None]
    if not geotagged:
        return [None] * len(photos)

    import reverse_geocode

    coords = [(p.latitude, p.longitude) for p in geotagged]
    results = reverse_geocode.search(coords)
    country_by_path = {
        str(photo.image_path): result["country"]
        for photo, result in zip(geotagged, results, strict=True)
    }

    donors = [p for p in geotagged if p.timestamp is not None]

    countries: list[str | None] = []
    for photo in photos:
        country = country_by_path.get(str(photo.image_path))
        if country is None and photo.timestamp is not None:
            country = _nearest_donor_country(photo.timestamp, donors, country_by_path)
        countries.append(country)
    return countries


def _nearest_donor_country(
    timestamp: datetime, donors: list[Photo], country_by_path: dict[str, str]
) -> str | None:
    best_country: str | None = None
    best_diff: float | None = None
    for donor in donors:
        diff = abs((donor.timestamp - timestamp).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_country = country_by_path[str(donor.image_path)]
    return best_country


def group_into_chapters(
    photos: list[Photo], countries: list[str | None]
) -> list[tuple[str | None, list[Photo]]]:
    """Group photos into contiguous runs of the same country label,
    preserving order. Does not merge non-adjacent runs of the same country
    (e.g. Italy, Italy, None, Italy produces three groups) -- deciding
    whether to render a repeat divider for a country that reappears after a
    None-labeled gap is a presentation choice, made by the caller.
    """
    return [
        (country, [photo for _, photo in group])
        for country, group in itertools.groupby(
            zip(countries, photos, strict=True), key=lambda pair: pair[0]
        )
    ]


CHAPTER_DIVIDER_PHOTO_COUNT = 3
# A panorama on the divider page spans the full-width bottom row instead
# of a single quadrant (a quarter of the page is too small a fraction to
# show one properly) -- costing both bottom quadrants at once, leaving
# room for at most one more (ordinary) photo alongside the title.
_PANORAMA_QUADRANT_COST = 2


def take_divider_photos(group_photos: list[Photo]) -> tuple[list[Photo], list[Photo]]:
    """Split a chapter's photos into (up to CHAPTER_DIVIDER_PHOTO_COUNT
    quadrant-units for the divider page, the rest), preserving order.
    Photos are taken from the front greedily, each spending from that
    shared budget: an ordinary photo costs 1 quadrant, a panorama costs
    _PANORAMA_QUADRANT_COST (only the first one encountered is ever
    eligible -- a second would need a whole page's worth of quadrants to
    itself). A photo that doesn't fit in whatever budget remains when it's
    reached -- including a force_solo=True photo, which wants a full page
    to itself, not to share a quadrant at all -- stays in its original
    relative position among "the rest" instead, to be handled by the
    normal build_pages() pass (which gives a panorama a full-width row
    paired with a couple of companions, or its own page).
    """
    divider_photos: list[Photo] = []
    remaining_photos: list[Photo] = []
    budget = CHAPTER_DIVIDER_PHOTO_COUNT
    panorama_taken = False
    for photo in group_photos:
        is_panorama = classify_photo(photo) == "panorama"
        cost = _PANORAMA_QUADRANT_COST if is_panorama else 1
        eligible = not photo.force_solo and not (is_panorama and panorama_taken) and cost <= budget
        if eligible:
            divider_photos.append(photo)
            budget -= cost
            panorama_taken = panorama_taken or is_panorama
        else:
            remaining_photos.append(photo)
    return divider_photos, remaining_photos
