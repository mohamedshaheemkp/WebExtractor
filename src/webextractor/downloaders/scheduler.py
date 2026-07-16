from __future__ import annotations

import asyncio

from webextractor.config import config
from webextractor.downloaders.queue import DownloadQueue
from webextractor.downloaders.retry import RetryHandler
from webextractor.downloaders.worker import DownloadWorker
from webextractor.models.asset import Asset


class DownloadScheduler:

    def __init__(
        self,
        downloader,
    ) -> None:

        self.downloader = downloader

    async def start(
        self,
        assets: list[Asset],
    ) -> None:

        queue = DownloadQueue()

        retry = RetryHandler(
            retries=config.retries,
        )

        for asset in assets:

            await queue.put(asset)

        workers = [

            asyncio.create_task(

                DownloadWorker(
                    self.downloader,
                    queue,
                    retry,
                ).run()

            )

            for _ in range(config.workers)

        ]

        await queue.join()

        for worker in workers:

            worker.cancel()

        await asyncio.gather(
            *workers,
            return_exceptions=True,
        )