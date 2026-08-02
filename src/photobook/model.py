from __future__ import annotations

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
    }
