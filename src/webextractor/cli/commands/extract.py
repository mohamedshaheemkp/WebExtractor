from __future__ import annotations

import asyncio
from pathlib import Path
from rich.console import Console

from webextractor.config import config
from webextractor.downloader.download import AssetDownloader
from webextractor.downloader.reports import write_reports
from webextractor.har.entries import HAREntryExtractor
from webextractor.har.normalizer import HARNormalizer
from webextractor.har.parser import HARParser
from webextractor.model.asset import Asset

console = Console(legacy_windows=False)


async def execute_extract(
    har_path: Path, output_dir: Path | None = None, workers: int | None = None
) -> None:
    if not har_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {har_path}")
        return

    base_output = output_dir if output_dir else config.output_dir
    target_output = base_output / har_path.stem
    target_output.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold cyan]Reading HAR file:[/bold cyan] {har_path}")
    parser = HARParser(har_path)
    entries = parser.get_entries()

    assets: list[Asset] = []
    seen_urls: set[str] = set()

    for entry in entries:
        url = HAREntryExtractor.get_url(entry)
        if not url:
            continue
        clean_url = HARNormalizer.normalize_url(url)
        if clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)

        mime = HAREntryExtractor.get_mime_type(entry)
        status = HAREntryExtractor.get_status(entry)
        size = HAREntryExtractor.get_size(entry)
        asset_type = HARNormalizer.classify_asset_type(clean_url, mime)

        assets.append(
            Asset(
                url=clean_url,
                original_url=url,
                asset_type=asset_type,
                mime_type=mime,
                status_code=status,
                size=size,
            )
        )

    console.print(f"[bold green]Discovered {len(assets)} unique assets.[/bold green]")

    downloader = AssetDownloader(output_dir=target_output, workers=workers or config.workers)
    console.print("[bold cyan]Starting asset download...[/bold cyan]")
    await downloader.download_all(assets, target_output)

    write_reports(assets, target_output)

    downloaded_cnt = sum(1 for a in assets if a.downloaded)
    console.print(f"\n[green]Total Assets Processed[/green] : {len(assets)}")
    console.print(f"[green]Successfully Downloaded[/green] : {downloaded_cnt}")
    console.print(f"[cyan]Output Directory[/cyan]       : {target_output.resolve()}\n")
