from enum import Enum, auto
from dataclasses import dataclass
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

    @classmethod
    def from_mime_or_ext(cls, content_type: str, path: Path) -> "AssetType":
        content_type = content_type.lower()

        # Check MIME type first
        if "text/html" in content_type:
            return cls.HTML
        if "text/css" in content_type:
            return cls.CSS
        if "javascript" in content_type:
            return cls.JS
        if "image/svg+xml" in content_type:
            return cls.SVG
        if "image/" in content_type:
            return cls.IMAGE
        if "font/" in content_type:
            return cls.FONT
        if "video/" in content_type:
            return cls.VIDEO
        if "application/json" in content_type or "text/json" in content_type:
            return cls.JSON
        if "application/wasm" in content_type:
            return cls.WASM

        # Fallback to file extension
        ext = path.suffix.lower()
        if ext in (".html", ".htm"):
            return cls.HTML
        if ext == ".css":
            return cls.CSS
        if ext in (".js", ".mjs"):
            return cls.JS
        if ext == ".svg":
            return cls.SVG
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"):
            return cls.IMAGE
        if ext in (".woff", ".woff2", ".ttf", ".otf", ".eot"):
            return cls.FONT
        if ext in (".mp4", ".webm", ".ogg", ".avi", ".mov"):
            return cls.VIDEO
        if ext == ".json":
            return cls.JSON
        if ext == ".wasm":
            return cls.WASM

        return cls.OTHER


@dataclass(slots=True)
class Asset:

    url: str

    local_path: Path

    content_type: str = ""

    status: int | None = None

    size: int = 0

    downloaded: bool = False

    @property
    def type(self) -> AssetType:
        return AssetType.from_mime_or_ext(self.content_type, self.local_path)