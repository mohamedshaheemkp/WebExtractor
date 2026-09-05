from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from webextractor.har.normalizer import HARNormalizer
from webextractor.model.asset import Asset


class NetworkInterceptor:
    """Interception and collection of network traffic during browser sessions."""

    def __init__(self) -> None:
        self.captured_assets: list[Asset] = []
        self._seen_urls: set[str] = set()

    def attach(self, page: Any) -> None:
        """Attach listeners to a Playwright page."""
        page.on("response", self._handle_response)

    async def _handle_response(self, response: Any) -> None:
        try:
            url = response.url
            if not url or url.startswith("data:") or url.startswith("blob:"):
                return

            clean_url = HARNormalizer.normalize_url(url)
            if clean_url in self._seen_urls:
                return
            self._seen_urls.add(clean_url)

            mime = response.headers.get("content-type", "")
            status = response.status
            parsed = urlparse(clean_url)
            asset_type = HARNormalizer.classify_asset_type(clean_url, mime)

            asset = Asset(
                url=clean_url,
                original_url=url,
                domain=parsed.netloc,
                path=parsed.path,
                filename=parsed.path.split("/")[-1] if "/" in parsed.path else "file",
                extension=parsed.path.split(".")[-1] if "." in parsed.path else "",
                asset_type=asset_type,
                mime_type=mime,
                status_code=status,
            )
            self.captured_assets.append(asset)
        except Exception:
            pass
