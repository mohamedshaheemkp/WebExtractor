from __future__ import annotations

import asyncio
import json
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiofiles
import aiohttp


class AssetPipeline:
    """
    Downloads all discovered website assets (images, videos, fonts, scripts)
    directly into the generated project's public/ folder and creates an asset manifest.
    """

    def __init__(self, output_dir: str | Path, concurrency: int = 8):
        self.output_dir = Path(output_dir)
        self.public_dir = self.output_dir / "public"
        self.concurrency = concurrency

    async def process_assets(
        self,
        assets_dict: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        for subdir in ("images", "videos", "fonts", "icons", "documents"):
            (self.public_dir / subdir).mkdir(parents=True, exist_ok=True)

        manifest: list[dict[str, Any]] = []
        tasks = []
        semaphore = asyncio.Semaphore(self.concurrency)

        async with aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        ) as session:
            for category, urls in assets_dict.items():
                target_sub = category if category in ("images", "videos", "fonts") else "images"
                for url in urls:
                    if not url.startswith("http"):
                        continue
                    tasks.append(self._download_asset(session, semaphore, url, target_sub, manifest))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        # Write analysis/assets.json manifest
        manifest_path = self.output_dir / "analysis" / "assets.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return manifest

    async def _download_asset(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        url: str,
        category: str,
        manifest: list[dict[str, Any]],
    ) -> None:
        async with semaphore:
            try:
                parsed = urlparse(url)
                filename = os.path.basename(parsed.path)
                if not filename or "." not in filename:
                    ext = mimetypes.guess_extension(category) or ".bin"
                    filename = f"asset_{abs(hash(url)) % 100000}{ext}"

                local_subpath = f"{category}/{filename}"
                dest_file = self.public_dir / local_subpath

                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        async with aiofiles.open(dest_file, "wb") as f:
                            await f.write(content)

                        manifest.append({
                            "source": url,
                            "local": f"/{local_subpath}",
                            "format": filename.split(".")[-1].lower() if "." in filename else "unknown",
                            "size_bytes": len(content),
                            "category": category,
                        })
            except Exception:
                pass
