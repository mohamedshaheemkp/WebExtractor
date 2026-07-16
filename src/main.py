from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from rich.console import Console

from webextractor.config import config
from webextractor.core.asset_manager import AssetManager
from webextractor.core.download_manager import DownloadManager
from webextractor.core.har import HARReader
from webextractor.extractors.har_extractor import HARExtractor
from webextractor.writers.report_writer import write_report
from webextractor.writers.text_writer import write_urls
from webextractor.writers.tree_writer import write_tree

console = Console()


async def run(file: Path) -> None:

    reader = HARReader(file)

    entries = reader.entries()

    manager = AssetManager()

    extractor = HARExtractor()

    extractor.extract(
        entries,
        manager,
    )

    assets = manager.assets

    await DownloadManager().download(
        assets,
    )

    write_urls(
        assets,
        config.output_dir,
    )

    from webextractor.writers.text_writer import write_failed

    write_failed(
        [
            asset
            for asset in assets
            if not asset.downloaded
        ],
        config.output_dir,
    )

    write_report(
        assets,
        config.output_dir,
    )

    write_tree(
        config.output_dir,
    )

    console.print()

    console.print(
        f"[green]Downloaded[/green] : {len(assets)}"
    )

    console.print(
        f"[cyan]Output[/cyan] : {config.output_dir}"
    )


def main() -> None:

    if len(sys.argv) < 2:

        console.print(
            "[red]Usage:[/red] python src/main.py <har file>"
        )

        return

    asyncio.run(
        run(
            Path(sys.argv[1])
        )
    )


if __name__ == "__main__":
    main()
    