from __future__ import annotations

import asyncio

from webextractor.models.asset import Asset


class DownloadQueue:

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Asset] = asyncio.Queue()

    async def put(self, asset: Asset) -> None:
        await self._queue.put(asset)

    async def get(self) -> Asset:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    async def join(self) -> None:
        await self._queue.join()

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()