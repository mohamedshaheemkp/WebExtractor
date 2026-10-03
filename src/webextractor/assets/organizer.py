from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from webextractor.model.asset import Asset, AssetType


class AssetOrganizer:
    """Organizes downloaded assets into public/ subdirectories with hard integrity guarantees."""

    @staticmethod
    def organize_assets(assets: list[Asset], project_dir: Path) -> list[dict[str, Any]]:
        public_dir = project_dir / "public"
        subdirs = {
            AssetType.IMAGE: public_dir / "images",
            AssetType.FONT: public_dir / "fonts",
            AssetType.VIDEO: public_dir / "videos",
            AssetType.DOCUMENT: public_dir / "documents",
            AssetType.JAVASCRIPT: public_dir / "scripts",
            AssetType.CSS: public_dir / "styles",
            AssetType.HTML: public_dir / "documents",
            AssetType.OTHER: public_dir / "misc",
        }

        for d in set(subdirs.values()):
            d.mkdir(parents=True, exist_ok=True)
        (public_dir / "icons").mkdir(parents=True, exist_ok=True)
        (public_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (public_dir / "styles").mkdir(parents=True, exist_ok=True)

        seen_dest_filenames: set[str] = set()

        for asset in assets:
            if not asset.downloaded or not asset.local_path or not asset.local_path.is_file():
                asset.downloaded = False
                asset.local_path = None
                asset.public_url = None
                continue

            # Strict evidence-based categorization: MIME type is authoritative over extension
            ext = (asset.extension or Path(urlparse(asset.url).path).suffix.lstrip(".")).lower()
            mime = (asset.mime_type or "").lower().split(";")[0].strip()

            # 1. Authoritative MIME type mapping
            if "javascript" in mime or "ecmascript" in mime:
                target_folder = public_dir / "scripts"
                asset.asset_type = AssetType.JAVASCRIPT
            elif "text/css" in mime or mime == "css":
                target_folder = public_dir / "styles"
                asset.asset_type = AssetType.CSS
            elif "text/html" in mime:
                target_folder = public_dir / "documents"
                asset.asset_type = AssetType.HTML
            elif "font" in mime or mime.startswith("application/font") or mime.startswith("application/x-font"):
                target_folder = public_dir / "fonts"
                asset.asset_type = AssetType.FONT
            elif mime.startswith("video/"):
                target_folder = public_dir / "videos"
                asset.asset_type = AssetType.VIDEO
            elif "image/svg" in mime or mime == "svg":
                target_folder = public_dir / "icons"
                asset.asset_type = AssetType.IMAGE
            elif mime.startswith("image/"):
                target_folder = public_dir / "images"
                asset.asset_type = AssetType.IMAGE
            elif "application/pdf" in mime or "application/json" in mime:
                target_folder = public_dir / "documents"
                asset.asset_type = AssetType.DOCUMENT
            # 2. Extension fallback when MIME is generic or absent
            elif ext in ("js", "mjs", "ts", "jsx", "tsx", "cjs"):
                target_folder = public_dir / "scripts"
                asset.asset_type = AssetType.JAVASCRIPT
            elif ext in ("css",):
                target_folder = public_dir / "styles"
                asset.asset_type = AssetType.CSS
            elif ext in ("html", "htm", "framercms"):
                target_folder = public_dir / "documents"
                asset.asset_type = AssetType.HTML
            elif ext in ("woff", "woff2", "ttf", "otf", "eot"):
                target_folder = public_dir / "fonts"
                asset.asset_type = AssetType.FONT
            elif ext in ("mp4", "webm", "ogg", "mov"):
                target_folder = public_dir / "videos"
                asset.asset_type = AssetType.VIDEO
            elif ext in ("svg",):
                target_folder = public_dir / "icons"
                asset.asset_type = AssetType.IMAGE
            elif ext in ("png", "jpg", "jpeg", "webp", "gif", "ico", "avif"):
                target_folder = public_dir / "images"
                asset.asset_type = AssetType.IMAGE
            elif ext in ("pdf", "txt", "xml", "json", "doc", "docx"):
                target_folder = public_dir / "documents"
                asset.asset_type = AssetType.DOCUMENT
            else:
                target_folder = subdirs.get(asset.asset_type, public_dir / "misc")

            folder_name = target_folder.name

            # Determine clean, collision-free filename preserving variant transformation evidence
            base_filename = asset.filename or Path(urlparse(asset.url).path).name or "asset.bin"
            parsed_q = urlparse(asset.url).query
            if parsed_q and "@" not in base_filename:
                m = re.search(r"(?:scale-down-to|width|w|size)=(\d+)", parsed_q, re.IGNORECASE)
                if m:
                    stem, f_ext = (base_filename.rsplit(".", 1) if "." in base_filename else (base_filename, ""))
                    base_filename = f"{stem}@{m.group(1)}{('.' + f_ext) if f_ext else ''}"

            clean_name = "".join(c for c in base_filename if c.isalnum() or c in ".-_@")
            if not clean_name:
                clean_name = f"asset_{abs(hash(asset.url)) % 100000}"
                if asset.extension:
                    clean_name += f".{asset.extension}"

            dest = target_folder / clean_name
            # If filename collision from another asset URL, disambiguate
            if dest.name in seen_dest_filenames and dest != asset.local_path:
                ext = dest.suffix
                stem = dest.stem
                disambiguated_name = f"{stem}_{abs(hash(asset.url)) % 10000}{ext}"
                dest = target_folder / disambiguated_name

            seen_dest_filenames.add(dest.name)

            if asset.local_path.resolve() != dest.resolve():
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(asset.local_path, dest)
                except Exception:
                    asset.downloaded = False
                    asset.local_path = None
                    asset.public_url = None
                    continue

            asset.local_path = dest
            asset.public_url = f"/{folder_name}/{dest.name}"

            # Hard invariant
            if asset.downloaded:
                assert asset.local_path is not None, f"Asset {asset.url} marked downloaded but local_path is None"
                assert asset.local_path.exists(), f"Asset {asset.url} local file {dest} does not exist"

        manifest: list[dict[str, Any]] = []
        for asset in assets:
            cat_name = asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)
            manifest.append({
                "source": asset.url,
                "local": asset.public_url if asset.downloaded else None,
                "downloaded": asset.downloaded,
                "category": cat_name,
                "size_bytes": asset.size,
            })

        # Save analysis/assets.json
        try:
            analysis_dir = project_dir / "analysis"
            analysis_dir.mkdir(parents=True, exist_ok=True)
            (analysis_dir / "assets.json").write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

        return manifest
