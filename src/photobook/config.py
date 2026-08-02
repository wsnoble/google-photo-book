from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


class BookConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "Photo Book"
    size: str = "8x10_landscape"
    cover: Literal["image_wrap", "dust_jacket"] = "image_wrap"


class LayoutConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hero_every: int | None = None


class CaptionsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True


class OrderingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: Literal["photoTakenTime"] = "photoTakenTime"


class PreferConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edited_images: bool = True


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    book: BookConfig = BookConfig()
    layout: LayoutConfig = LayoutConfig()
    captions: CaptionsConfig = CaptionsConfig()
    ordering: OrderingConfig = OrderingConfig()
    prefer: PreferConfig = PreferConfig()


def load_config(path: Path | None) -> Config:
    if path is None:
        return Config()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config.model_validate(data)
