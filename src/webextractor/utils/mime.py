from pathlib import Path

from webextractor.model.asset import AssetType


def classify(mime: str, filename: str = "") -> AssetType:

    mime = (mime or "").lower()

    extension = Path(filename).suffix.lower()

    # ---------- HTML ----------

    if "text/html" in mime:
        return AssetType.HTML

    # ---------- CSS ----------

    if "text/css" in mime or extension == ".css":
        return AssetType.CSS

    # ---------- JavaScript ----------

    if (
        "javascript" in mime
        or extension in {".js", ".mjs"}
    ):
        return AssetType.JS

    # ---------- Images ----------

    if "image/" in mime:
        if "svg" in mime:
            return AssetType.SVG

        return AssetType.IMAGE

    if extension == ".svg":
        return AssetType.SVG

    if extension in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".avif",
        ".ico",
    }:
        return AssetType.IMAGE

    # ---------- Fonts ----------

    if "font/" in mime:
        return AssetType.FONT

    if extension in {
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
    }:
        return AssetType.FONT

    # ---------- Video ----------

    if "video/" in mime:
        return AssetType.VIDEO

    if extension in {
        ".mp4",
        ".webm",
        ".mov",
        ".m4v",
    }:
        return AssetType.VIDEO

    # ---------- JSON ----------

    if "json" in mime:
        return AssetType.JSON

    if extension == ".json":
        return AssetType.JSON

    # ---------- WASM ----------

    if "wasm" in mime or extension == ".wasm":
        return AssetType.WASM

    return AssetType.OTHER