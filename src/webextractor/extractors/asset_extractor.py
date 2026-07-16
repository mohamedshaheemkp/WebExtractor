from pathlib import Path
from urllib.parse import urlparse

from webextractor.models.asset import Asset
from webextractor.utils.path import url_to_path
from webextractor.config import config


def extract_assets(entries: list[dict]) -> list[Asset]:

    assets: list[Asset] = []

    for entry in entries:

        request = entry.get("request", {})
        response = entry.get("response", {})
        content = response.get("content", {})

        url = request.get("url")

        if not url:
            continue

        local_path = url_to_path(url, config.output_dir)

        assets.append(
            Asset(
                url=url,
                local_path=local_path,
                content_type=content.get("mimeType", ""),
                status=response.get("status", 0),
                size=content.get("size", 0),
            )
        )

    return assets