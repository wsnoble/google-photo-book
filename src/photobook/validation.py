from __future__ import annotations

import csv
import json
from pathlib import Path

from photobook.importer import ImportResult
from photobook.model import photo_to_dict


def write_photos_json(result: ImportResult, path: Path) -> None:
    data = [photo_to_dict(photo) for photo in result.photos]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_report_csv(result: ImportResult, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["image_path", "timestamp", "timestamp_source", "caption", "edited", "warnings"]
        )
        for photo in result.photos:
            writer.writerow(
                [
                    str(photo.image_path),
                    photo.timestamp.isoformat() if photo.timestamp else "",
                    photo.timestamp_source,
                    photo.caption or "",
                    photo.edited,
                    "; ".join(photo.warnings),
                ]
            )


def summarize(result: ImportResult) -> dict[str, int]:
    photos = result.photos
    return {
        "printable_images": len(photos),
        "videos_skipped": len(result.videos_skipped),
        "captions_found": sum(1 for p in photos if p.caption),
        "captions_missing": sum(1 for p in photos if not p.caption),
        "metadata_inherited": sum(1 for p in photos if p.edited and p.metadata_path is not None),
        "unmatched_images": len(result.unmatched_images),
        "unused_json_files": len(result.unused_json_files),
    }


def write_report_txt(result: ImportResult, path: Path) -> None:
    lines = [f"{key}: {value}" for key, value in summarize(result).items()]

    if result.unmatched_images:
        lines.append("")
        lines.append("Unmatched images:")
        lines.extend(f"  {p}" for p in result.unmatched_images)

    if result.unused_json_files:
        lines.append("")
        lines.append("Unused JSON files:")
        lines.extend(f"  {p}" for p in result.unused_json_files)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
