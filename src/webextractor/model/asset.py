from __future__ import annotations

from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field


class AssetType(str, Enum):
    HTML = "html"
    CSS = "css"
    JAVASCRIPT = "javascript"
    IMAGE = "image"
    VIDEO = "video"
    FONT = "font"
    API = "api"
    DOCUMENT = "document"
    OTHER = "other"


class Asset(BaseModel):
    url: str
    original_url: str = ""
    domain: str = ""
    path: str = ""
    filename: str = ""
    extension: str = ""
    asset_type: AssetType = AssetType.OTHER
    mime_type: str | None = None
    status_code: int | None = None
    size: int = 0
    downloaded: bool = False
    local_path: Path | None = None
    public_url: str | None = None

    class Config:
        arbitrary_types_allowed = True
