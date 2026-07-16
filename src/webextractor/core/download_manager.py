from __future__ import annotations

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from webextractor.core.mirror import Mirror
from webextractor.core.session import create_session
from webextractor.downloaders.downloader import Downloader
from webextractor.downloaders.scheduler import DownloadScheduler
from webextractor.models.asset import Asset


class DownloadManager:

    async def download(
        self,
        assets: list[Asset],
    ) -> None:

        Mirror().prepare_many(assets)

        async with create_session() as session:

            downloader = Downloader(session)

            scheduler = DownloadScheduler(
                downloader,
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold cyan]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
            ) as progress:

                task = progress.add_task(
                    "Downloading",
                    total=len(assets),
                )

                original = downloader.download

                async def wrapped(asset):

                    result = await original(asset)

                    progress.advance(task)

                    return result

                downloader.download = wrapped

                await scheduler.start(
                    assets,
                )
                downloaded = sum(
                    1
                    for asset in assets
                    if asset.downloaded
                )

                failed = len(assets) - downloaded

                progress.console.print()

                progress.console.print(
                    f"[green]Downloaded[/green] : {downloaded}"
                )

                progress.console.print(
                    f"[red]Failed[/red] : {failed}"
                )