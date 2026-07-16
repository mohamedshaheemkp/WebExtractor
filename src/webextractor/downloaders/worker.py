from __future__ import annotations

from webextractor.downloaders.downloader import Downloader
from webextractor.downloaders.queue import DownloadQueue
from webextractor.downloaders.retry import RetryHandler
from webextractor.models.asset import Asset
from webextractor.utils.filesystem import exists
from webextractor.utils.logger import logger


class DownloadWorker:

    def __init__(
        self,
        downloader: Downloader,
        queue: DownloadQueue,
        retry: RetryHandler,
    ) -> None:

        self.downloader = downloader
        self.queue = queue
        self.retry = retry

    async def run(self) -> None:

        while True:

            asset: Asset = await self.queue.get()

            try:

                if asset.local_path and exists(asset.local_path):

                    logger.info(
                        "Skip : %s",
                        asset.filename,
                    )

                    self.queue.task_done()
                    continue

                await self.retry.run(
                    self.downloader.download,
                    asset,
                )

            finally:

                self.queue.task_done()