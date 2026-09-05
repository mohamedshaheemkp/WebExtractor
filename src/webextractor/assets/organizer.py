from __future__ import annotations

import json
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
        }

        for d in set(subdirs.values()):
            d.mkdir(parents=True, exist_ok=True)
        (public_dir / "icons").mkdir(parents=True, exist_ok=True)

        seen_dest_filenames: set[str] = set()

        for asset in assets:
            if not asset.downloaded or not asset.local_path or not asset.local_path.exists():
                asset.downloaded = False
                asset.local_path = None
                asset.public_url = None
                continue

            target_folder = subdirs.get(asset.asset_type, public_dir / "images")
            folder_name = target_folder.name

            # Determine clean, collision-free filename
            base_filename = asset.filename or Path(urlparse(asset.url).path).name or "asset.bin"
            clean_name = "".join(c for c in base_filename if c.isalnum() or c in ".-_")
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
                try:
                    shutil.copy2(asset.local_path, dest)
                except Exception:
                    pass

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
