from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

TimestampSource = Literal["photoTakenTime", "creationTime", "exif", "unknown"]


@dataclass
class Photo:
    image_path: Path
    metadata_path: Path | None
    timestamp: datetime | None
    timestamp_source: TimestampSource
    caption: str | None
    google_photos_url: str | None
    width: int
    height: int
    orientation: int
    edited: bool
    warnings: list[str] = field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    # Review-time layout override (see review.py): True forces the photo
    # onto its own page, False forces it to never be alone on a page, None
    # (default) leaves it to the automatic panorama-based decision in
    # layout.py. Not a raw imported fact, so it's never set during import
    # and deliberately left out of photo_to_dict/dict_to_photo -- it's
    # always None for a freshly-imported photo.
    force_solo: bool | None = None


def photo_to_dict(photo: Photo) -> dict:
    return {
        "image_path": str(photo.image_path),
        "metadata_path": str(photo.metadata_path) if photo.metadata_path else None,
        "timestamp": photo.timestamp.isoformat() if photo.timestamp else None,
        "timestamp_source": photo.timestamp_source,
        "caption": photo.caption,
        "google_photos_url": photo.google_photos_url,
        "width": photo.width,
        "height": photo.height,
        "orientation": photo.orientation,
        "edited": photo.edited,
        "warnings": list(photo.warnings),
        "latitude": photo.latitude,
        "longitude": photo.longitude,
    }


def dict_to_photo(data: dict) -> Photo:
    return Photo(
        image_path=Path(data["image_path"]),
        metadata_path=Path(data["metadata_path"]) if data.get("metadata_path") else None,
        timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
        timestamp_source=data["timestamp_source"],
        caption=data.get("caption"),
        google_photos_url=data.get("google_photos_url"),
        width=data["width"],
        height=data["height"],
        orientation=data["orientation"],
        edited=data["edited"],
        warnings=list(data.get("warnings", [])),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
    )


def load_photos(path: Path) -> list[Photo]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [dict_to_photo(item) for item in data]
