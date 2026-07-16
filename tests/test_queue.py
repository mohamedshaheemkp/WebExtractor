import asyncio

from webextractor.downloaders.queue import DownloadQueue
from webextractor.models.asset import Asset
from webextractor.models.asset import AssetType


async def main():

    queue = DownloadQueue()

    asset = Asset(
        url="https://example.com",
        original_url="https://example.com",
        domain="example.com",
        path="/",
        filename="index.html",
        extension="html",
        asset_type=AssetType.HTML,
    )

    await queue.put(asset)

    print(queue.qsize())

    item = await queue.get()

    print(item.url)

    queue.task_done()

    await queue.join()


asyncio.run(main())