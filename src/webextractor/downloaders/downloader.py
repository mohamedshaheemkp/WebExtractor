from __future__ import annotations

import aiofiles
import aiohttp

from webextractor.config import config
from webextractor.models.asset import Asset
from webextractor.utils.filesystem import ensure_parent
from webextractor.utils.logger import logger


class Downloader:

    def __init__(
        self,
        session: aiohttp.ClientSession,
    ) -> None:

        self.session = session

    async def download(
        self,
        asset: Asset,
    ) -> bool:

        if asset.local_path is None:
            raise ValueError("Asset local_path is not set.")

        ensure_parent(asset.local_path)

        try:

            async with self.session.get(asset.url) as response:

                if response.status != 200:

                    logger.warning(
                        "%s -> %s",
                        response.status,
                        asset.url,
                    )

                    return False
                written = 0

                async with aiofiles.open(
                    asset.local_path,
                    "wb",
                ) as file:

                    async for chunk in response.content.iter_chunked(
                        config.download_chunk_size
                    ):

                        await file.write(chunk)

                        written += len(chunk)

                asset.status_code = response.status
                asset.size = written
                asset.downloaded = True

                logger.debug(
                    "Downloaded : %s",
                    asset.filename,
                )

                if asset.size == 0:

                    logger.warning(
                        "Empty File : %s",
                        asset.filename,
                    )

                    return False
                    
                if asset.size <= 0:

                    logger.warning(
                        "Empty file : %s",
                        asset.url,
                    )

                    return False

                return True

        except Exception as error:

            logger.error(
                "%s -> %s",
                asset.url,
                error,
            )

            return False