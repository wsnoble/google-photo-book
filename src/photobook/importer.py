from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pillow_heif
from PIL import Image

from photobook.model import Photo, TimestampSource

pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".webm"}
EDITED_SUFFIX = "-edited"

_ORIENTATION_TAG = 274  # EXIF "Orientation"
_DATETIME_ORIGINAL_TAG = 36867
_DATETIME_TAG = 306
_DUPLICATE_SUFFIX_RE = re.compile(r"^(?P<base>.+)\((?P<n>\d+)\)$")


@dataclass
class ImportResult:
    photos: list[Photo]
    videos_skipped: list[Path] = field(default_factory=list)
    unmatched_images: list[Path] = field(default_factory=list)
    unused_json_files: list[Path] = field(default_factory=list)


def scan_album(root: Path, *, prefer_edited: bool = True) -> ImportResult:
    """Scan a Google Takeout album export and build the list of importable photos.

    Groups an image's `-edited` variant with its original so only one of the
    pair is selected (per `prefer_edited`), while duplicate-suffixed files
    like `IMG_0001(1).jpg` are treated as distinct photos.
    """
    root = Path(root)
    image_groups: dict[tuple[Path, str, str], dict[str, Path]] = {}
    videos_skipped: list[Path] = []
    all_json_files: set[Path] = set()

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".json":
            all_json_files.add(path)
            continue
        if suffix in VIDEO_EXTENSIONS:
            videos_skipped.append(path)
            continue
        if suffix not in IMAGE_EXTENSIONS:
            continue

        edited = path.stem.endswith(EDITED_SUFFIX)
        group_stem = path.stem[: -len(EDITED_SUFFIX)] if edited else path.stem
        key = (path.parent, group_stem, path.suffix)
        image_groups.setdefault(key, {})["edited" if edited else "original"] = path

    photos: list[Photo] = []
    unmatched_images: list[Path] = []
    used_json_files: set[Path] = set()

    for (directory, group_stem, ext), variants in sorted(image_groups.items()):
        original = variants.get("original")
        edited_path = variants.get("edited")

        if prefer_edited and edited_path is not None:
            selected_path, is_edited = edited_path, True
        elif original is not None:
            selected_path, is_edited = original, False
        else:
            selected_path, is_edited = edited_path, True  # type: ignore[assignment]

        metadata_path = _find_metadata(directory, group_stem, ext)
        photo = _build_photo(selected_path, metadata_path, is_edited)

        if metadata_path is None:
            unmatched_images.append(selected_path)
        else:
            used_json_files.add(metadata_path)
        photos.append(photo)

    unused_json_files = sorted(all_json_files - used_json_files)

    return ImportResult(
        photos=photos,
        videos_skipped=videos_skipped,
        unmatched_images=unmatched_images,
        unused_json_files=unused_json_files,
    )


def _metadata_candidates(directory: Path, group_stem: str, ext: str) -> list[Path]:
    original_name = f"{group_stem}{ext}"
    candidates = [
        directory / f"{original_name}.supplemental-metadata.json",
        directory / f"{original_name}.json",
    ]

    # Google Takeout renames the JSON for numbered duplicates by moving the
    # "(n)" counter after the image extension, e.g. IMG_0001(1).jpg's
    # metadata is IMG_0001.jpg(1).json rather than IMG_0001(1).jpg.json.
    match = _DUPLICATE_SUFFIX_RE.match(group_stem)
    if match:
        base_name = f"{match['base']}{ext}"
        n = match["n"]
        candidates += [
            directory / f"{base_name}.supplemental-metadata({n}).json",
            directory / f"{base_name}({n}).json",
        ]

    return candidates


def _find_metadata(directory: Path, group_stem: str, ext: str) -> Path | None:
    for candidate in _metadata_candidates(directory, group_stem, ext):
        if candidate.is_file():
            return candidate
    return None


def _build_photo(image_path: Path, metadata_path: Path | None, edited: bool) -> Photo:
    metadata = _load_metadata(metadata_path) if metadata_path else {}

    caption = (metadata.get("description") or "").strip() or None
    google_photos_url = metadata.get("url")
    timestamp, timestamp_source = _resolve_timestamp(metadata, image_path)
    width, height, orientation = _read_image_info(image_path)

    warnings: list[str] = []
    if metadata_path is None:
        warnings.append("no metadata file matched")
    if caption is None:
        warnings.append("no caption")
    if timestamp_source == "unknown":
        warnings.append("timestamp unknown")
    if width == 0 or height == 0:
        warnings.append("failed to read image dimensions")

    return Photo(
        image_path=image_path,
        metadata_path=metadata_path,
        timestamp=timestamp,
        timestamp_source=timestamp_source,
        caption=caption,
        google_photos_url=google_photos_url,
        width=width,
        height=height,
        orientation=orientation,
        edited=edited,
        warnings=warnings,
    )


def _load_metadata(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("failed to read metadata %s: %s", path, exc)
        return {}


def _resolve_timestamp(metadata: dict, image_path: Path) -> tuple[datetime | None, TimestampSource]:
    for key in ("photoTakenTime", "creationTime"):
        block = metadata.get(key)
        timestamp_str = block.get("timestamp") if block else None
        if timestamp_str:
            try:
                return datetime.fromtimestamp(int(timestamp_str), tz=UTC), key
            except (TypeError, ValueError):
                continue

    exif_timestamp = _read_exif_timestamp(image_path)
    if exif_timestamp is not None:
        return exif_timestamp, "exif"

    return None, "unknown"


def _read_exif_timestamp(image_path: Path) -> datetime | None:
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            raw = exif.get(_DATETIME_ORIGINAL_TAG) or exif.get(_DATETIME_TAG)
    except Exception as exc:
        logger.warning("failed to read EXIF from %s: %s", image_path, exc)
        return None

    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("ascii", errors="ignore")
    try:
        # EXIF has no timezone field; treat it as UTC (best-effort) so it stays
        # comparable with the timezone-aware timestamps from Takeout's JSON.
        return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S").replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _read_image_info(image_path: Path) -> tuple[int, int, int]:
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            orientation = img.getexif().get(_ORIENTATION_TAG, 1)
        return width, height, orientation
    except Exception as exc:
        logger.warning("failed to read image %s: %s", image_path, exc)
        return 0, 0, 1
