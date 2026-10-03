from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import aiofiles
import aiohttp

from webextractor.assets.concurrency import ConcurrencyManager
from webextractor.config import config
from webextractor.model.asset import Asset


class AssetDownloader:
    """Asynchronous HTTP asset downloader with retries and local file mirroring."""

    def __init__(self, output_dir: Path | None = None, workers: int = 8) -> None:
        self.output_dir = output_dir or config.output_dir
        self.workers = workers

    def prepare_local_path(self, asset: Asset, output_dir: Path) -> Path:
        parsed = urlparse(asset.url)
        domain = parsed.netloc or "assets"
        path = parsed.path.lstrip("/")

        if not path or path.endswith("/"):
            path += "index.html"

        # Sanitize path to remove special characters
        sanitized_parts = []
        for part in path.split("/"):
            clean_part = "".join(c for c in part if c.isalnum() or c in ".-_")
            if not clean_part:
                clean_part = "file"
            sanitized_parts.append(clean_part)

        # Preserve variant transformation parameters so variants never overwrite each other
        variant_suffix = ""
        if parsed.query:
            m = re.search(r"(?:scale-down-to|width|w|size)=(\d+)", parsed.query, re.IGNORECASE)
            if m:
                variant_suffix = f"@{m.group(1)}"
            elif parsed.query.strip():
                q_hash = abs(hash(parsed.query)) % 10000
                variant_suffix = f"_{q_hash}"

        if variant_suffix and sanitized_parts:
            last = sanitized_parts[-1]
            if "." in last:
                stem, ext = last.rsplit(".", 1)
                sanitized_parts[-1] = f"{stem}{variant_suffix}.{ext}"
            else:
                sanitized_parts[-1] = f"{last}{variant_suffix}"

        file_path = output_dir / domain / Path(*sanitized_parts)
        if file_path.exists() and file_path.is_dir():
            file_path = file_path / "index.bin"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        asset.local_path = file_path
        asset.domain = domain
        asset.filename = file_path.name
        asset.extension = file_path.suffix.lstrip(".")
        return file_path

    async def download_single(
        self, session: aiohttp.ClientSession, asset: Asset, max_retries: int = 3
    ) -> bool:
        if not asset.local_path:
            self.prepare_local_path(asset, self.output_dir)

        assert asset.local_path is not None

        # If file already exists and has content, skip downloading
        if asset.local_path.is_file() and asset.local_path.stat().st_size > 0:
            asset.downloaded = True
            asset.size = asset.local_path.stat().st_size
            return True

        for attempt in range(max_retries):
            try:
                timeout = aiohttp.ClientTimeout(total=config.timeout)
                headers = {"User-Agent": config.user_agent}
                async with session.get(asset.url, headers=headers, timeout=timeout) as response:
                    asset.status_code = response.status
                    if response.status == 200:
                        written = 0
                        async with aiofiles.open(asset.local_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(config.download_chunk_size):
                                await f.write(chunk)
                                written += len(chunk)
                        asset.size = written
                        asset.downloaded = True
                        return True
                    elif response.status in (403, 404, 410):
                        # Client error, don't retry endlessly
                        return False
            except Exception:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt * 0.5)
                else:
                    return False
        return False

    async def download_all(
        self,
        assets: list[Asset],
        output_dir: Path | None = None,
        progress_callback: Any = None,
    ) -> list[Asset]:
        target_dir = output_dir or self.output_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        for asset in assets:
            self.prepare_local_path(asset, target_dir)

        concurrency = ConcurrencyManager(max_workers=self.workers)

        connector = aiohttp.TCPConnector(limit=config.connections, ssl=config.verify_ssl)
        async with aiohttp.ClientSession(connector=connector) as session:
            async def worker(asset: Asset) -> bool:
                return await self.download_single(session, asset, max_retries=config.retries)

            await concurrency.run(assets, worker, progress_callback=progress_callback)

        return assets
