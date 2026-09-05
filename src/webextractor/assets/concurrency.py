from __future__ import annotations

import asyncio
from typing import Callable, Coroutine, Any

from webextractor.model.asset import Asset


class ConcurrencyManager:
    """Manages concurrent download workers using an asyncio Queue."""

    def __init__(self, max_workers: int = 8) -> None:
        self.max_workers = max_workers
        self.queue: asyncio.Queue[Asset] = asyncio.Queue()

    async def run(
        self,
        assets: list[Asset],
        worker_fn: Callable[[Asset], Coroutine[Any, Any, bool]],
        progress_callback: Callable[[Asset, bool], None] | None = None,
    ) -> list[Asset]:
        for asset in assets:
            await self.queue.put(asset)

        async def worker() -> None:
            while True:
                try:
                    asset = await self.queue.get()
                except asyncio.CancelledError:
                    break

                try:
                    success = await worker_fn(asset)
                    if progress_callback:
                        progress_callback(asset, success)
                except Exception:
                    if progress_callback:
                        progress_callback(asset, False)
                finally:
                    self.queue.task_done()

        tasks = [asyncio.create_task(worker()) for _ in range(min(self.max_workers, len(assets) or 1))]

        await self.queue.join()

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        return assets
