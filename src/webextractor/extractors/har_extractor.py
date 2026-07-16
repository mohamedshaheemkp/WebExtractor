from __future__ import annotations

from webextractor.core.asset_manager import AssetManager
from webextractor.models.asset import Asset
from webextractor.utils.filter import should_download
from webextractor.utils.mime import classify
from webextractor.utils.url import domain
from webextractor.utils.url import extension
from webextractor.utils.url import filename
from webextractor.utils.url import normalize
from webextractor.utils.url import path


class HARExtractor:

    def extract(self, entries: list[dict], manager: AssetManager) -> None:

        for entry in entries:

            request = entry.get("request", {})
            response = entry.get("response", {})
            content = response.get("content", {})

            url = normalize(request.get("url", ""))

            if not url:
                continue

            mime = content.get("mimeType", "")

            status = response.get("status")

            if not should_download(
                url,
                status,
            ):
                continue

            manager.add(
                Asset(
                    url=url,
                    original_url=request.get("url", ""),
                    domain=domain(url),
                    path=path(url),
                    filename=filename(url),
                    extension=extension(filename(url)),
                    asset_type=classify(
                        mime,
                        filename(url),
                    ),
                    mime_type=mime,
                    status_code=status,
                    size=content.get("size", 0),
                )
            )