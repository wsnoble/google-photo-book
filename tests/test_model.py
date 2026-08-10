from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from photobook.importer import ImportResult
from photobook.model import Photo, dict_to_photo, load_photos, photo_to_dict
from photobook.validation import write_photos_json


def _sample_photo() -> Photo:
    return Photo(
        image_path=Path("/album/IMG_0001.jpg"),
        metadata_path=Path("/album/IMG_0001.jpg.supplemental-metadata.json"),
        timestamp=datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC),
        timestamp_source="photoTakenTime",
        caption="A test caption",
        google_photos_url="https://photos.google.com/photo/AAA",
        width=800,
        height=600,
        orientation=1,
        edited=False,
        warnings=["timestamp unknown"],
        latitude=44.1236889,
        longitude=9.7181139,
    )


def test_dict_to_photo_round_trips_photo_to_dict() -> None:
    photo = _sample_photo()

    round_tripped = dict_to_photo(photo_to_dict(photo))

    assert round_tripped == photo


def test_dict_to_photo_handles_missing_lat_lon_keys() -> None:
    # A photos.json written before latitude/longitude existed won't have
    # these keys at all -- must load as None, not KeyError.
    data = photo_to_dict(_sample_photo())
    del data["latitude"]
    del data["longitude"]

    photo = dict_to_photo(data)

    assert photo.latitude is None
    assert photo.longitude is None


def test_dict_to_photo_handles_missing_metadata_and_timestamp() -> None:
    photo = Photo(
        image_path=Path("/album/IMG_0004.jpg"),
        metadata_path=None,
        timestamp=None,
        timestamp_source="unknown",
        caption=None,
        google_photos_url=None,
        width=0,
        height=0,
        orientation=1,
        edited=False,
    )

    round_tripped = dict_to_photo(photo_to_dict(photo))

    assert round_tripped == photo


def test_load_photos_reads_back_what_write_photos_json_wrote(tmp_path: Path) -> None:
    photo = _sample_photo()
    result = ImportResult(photos=[photo])
    out = tmp_path / "photos.json"

    write_photos_json(result, out)
    loaded = load_photos(out)

    assert loaded == [photo]
