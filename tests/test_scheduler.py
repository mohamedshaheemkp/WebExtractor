import asyncio

from webextractor.core.mirror import Mirror
from webextractor.core.session import create_session
from webextractor.downloaders.downloader import Downloader
from webextractor.downloaders.scheduler import DownloadScheduler
from webextractor.models.asset import Asset
from webextractor.models.asset import AssetType


async def main():

    asset = Asset(
        url="https://www.google.com/favicon.ico",
        original_url="https://www.google.com/favicon.ico",
        domain="google.com",
        path="/favicon.ico",
        filename="favicon.ico",
        extension="ico",
        asset_type=AssetType.IMAGE,
    )

    Mirror().prepare(asset)

    async with create_session() as session:

        downloader = Downloader(session)

        scheduler = DownloadScheduler(
            downloader,
        )

        await scheduler.start([asset])


asyncio.run(main())