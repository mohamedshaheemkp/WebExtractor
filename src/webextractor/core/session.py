from __future__ import annotations

import aiohttp

from webextractor.config import config


def create_session() -> aiohttp.ClientSession:

    timeout = aiohttp.ClientTimeout(
        total=config.timeout,
    )

    connector = aiohttp.TCPConnector(
        limit=config.connections,
        ssl=config.verify_ssl,
    )

    return aiohttp.ClientSession(
        timeout=timeout,
        connector=connector,
        headers={
            "User-Agent": config.user_agent,
        },
    )