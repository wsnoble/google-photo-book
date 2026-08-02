from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from photobook.config import Config, load_config


def test_load_config_with_no_path_returns_defaults() -> None:
    config = load_config(None)

    assert config == Config()
    assert config.prefer.edited_images is True
    assert config.book.size == "8x10_landscape"
    assert config.book.cover == "image_wrap"


def test_load_config_reads_yaml_file(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
book:
  title: GERT Highlights
  size: 8x10_landscape
  cover: image_wrap

layout:
  hero_every: 12

captions:
  enabled: true

ordering:
  by: photoTakenTime

prefer:
  edited_images: false
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.book.title == "GERT Highlights"
    assert config.layout.hero_every == 12
    assert config.prefer.edited_images is False


def test_unknown_config_key_raises_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("book:\n  title: Test\n  unknown_field: oops\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(path)
