from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


class AssetType(Enum):
    HTML = auto()
    CSS = auto()
    JS = auto()
    IMAGE = auto()
    FONT = auto()
    VIDEO = auto()
    JSON = auto()
    SVG = auto()
    WASM = auto()
    OTHER = auto()


@dataclass(slots=True)
class Asset:
    url: str
    original_url: str
    domain: str
    path: str
    filename: str
    extension: str
    asset_type: AssetType
    mime_type: str = ""
    status_code: int | None = None
    size: int = 0
    discovered_from: str = "HAR"
    local_path: Path | None = None
    downloaded: bool = False