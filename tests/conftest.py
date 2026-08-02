from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image


def _write_image(path: Path, size: tuple[int, int]) -> None:
    Image.new("RGB", size, (128, 64, 32)).save(path)


def _write_json(path: Path, **fields: object) -> None:
    path.write_text(json.dumps(fields), encoding="utf-8")


@pytest.fixture
def sample_takeout(tmp_path: Path) -> Path:
    """A small, synthetic Google Takeout album covering the tricky cases:
    a normal photo, an edited pair, duplicate-suffixed files, a photo with
    no metadata sidecar, an orphan metadata file, and a skipped video.
    """
    album = tmp_path / "Takeout" / "Google Photos" / "Sample Album"
    album.mkdir(parents=True)

    # 1. Normal photo with matching metadata.
    _write_image(album / "IMG_0001.jpg", (800, 600))
    _write_json(
        album / "IMG_0001.jpg.supplemental-metadata.json",
        title="IMG_0001.jpg",
        description="A normal photo",
        photoTakenTime={"timestamp": "1700000000"},
        creationTime={"timestamp": "1700000100"},
        url="https://photos.google.com/photo/AAA",
    )

    # 2. Edited pair: original + edited variant, metadata lives on the original.
    _write_image(album / "IMG_0002.jpg", (600, 800))
    _write_image(album / "IMG_0002-edited.jpg", (600, 800))
    _write_json(
        album / "IMG_0002.jpg.supplemental-metadata.json",
        title="IMG_0002.jpg",
        description="An edited photo",
        photoTakenTime={"timestamp": "1700000200"},
        creationTime={"timestamp": "1700000300"},
        url="https://photos.google.com/photo/BBB",
    )

    # 3. Duplicate-suffixed files: two distinct photos sharing a base filename.
    _write_image(album / "IMG_0003.jpg", (800, 800))
    _write_json(
        album / "IMG_0003.jpg.supplemental-metadata.json",
        title="IMG_0003.jpg",
        description="First copy",
        photoTakenTime={"timestamp": "1700000400"},
        creationTime={"timestamp": "1700000500"},
        url="https://photos.google.com/photo/CCC",
    )
    _write_image(album / "IMG_0003(1).jpg", (800, 800))
    _write_json(
        album / "IMG_0003.jpg(1).json",
        title="IMG_0003(1).jpg",
        description="Second copy",
        photoTakenTime={"timestamp": "1700000600"},
        creationTime={"timestamp": "1700000700"},
        url="https://photos.google.com/photo/DDD",
    )

    # 4. Photo with no metadata sidecar at all.
    _write_image(album / "IMG_0004.jpg", (1000, 500))

    # 5. Orphan metadata file with no matching image (an "unused JSON file").
    _write_json(
        album / "IMG_0005.jpg.supplemental-metadata.json",
        title="IMG_0005.jpg",
        description="Orphan metadata",
        photoTakenTime={"timestamp": "1700000800"},
    )

    # 6. Video, which should be skipped entirely.
    (album / "MVI_0006.mp4").write_bytes(b"not a real video, just needs to exist")

    return album
