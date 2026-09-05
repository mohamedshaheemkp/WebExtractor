from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from webextractor.model.asset import AssetType


class HARNormalizer:
    """URL normalization and MIME classification."""

    @staticmethod
    def normalize_url(url: str) -> str:
        if not url:
            return ""

        url = url.strip()
        parsed = urlparse(url)

        # Drop fragments
        clean_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            "",
        ))

        return clean_url

    @staticmethod
    def classify_asset_type(url: str, mime_type: str | None = None) -> AssetType:
        lower_url = url.lower().split("?")[0]
        lower_mime = (mime_type or "").lower()

        if "text/html" in lower_mime or lower_url.endswith((".html", ".htm")):
            return AssetType.HTML

        if "text/css" in lower_mime or lower_url.endswith(".css"):
            return AssetType.CSS

        if (
            "javascript" in lower_mime
            or "ecmascript" in lower_mime
            or lower_url.endswith((".js", ".mjs", ".jsx", ".ts", ".tsx"))
        ):
            return AssetType.JAVASCRIPT

        if lower_mime.startswith("image/") or lower_url.endswith(
            (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".avif", ".bmp")
        ):
            return AssetType.IMAGE

        if lower_mime.startswith("video/") or lower_url.endswith(
            (".mp4", ".webm", ".mov", ".m3u8", ".ts", ".mkv")
        ):
            return AssetType.VIDEO

        if lower_mime.startswith("font/") or lower_url.endswith(
            (".woff", ".woff2", ".ttf", ".otf", ".eot")
        ):
            return AssetType.FONT

        if "application/json" in lower_mime or lower_url.endswith(".json"):
            return AssetType.API

        if "application/pdf" in lower_mime or lower_url.endswith((".pdf", ".doc", ".docx")):
            return AssetType.DOCUMENT

        return AssetType.OTHER
