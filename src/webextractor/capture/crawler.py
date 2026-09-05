from __future__ import annotations

from pathlib import Path

from .browser import BrowserCapture
from .multi_viewport import MultiViewportCapture
from .snapshot import SnapshotWriter


class WebsiteCrawler:

    def __init__(
        self,
        output_dir: str | Path,
    ):
        self.output_dir = Path(output_dir)

    async def crawl(
        self,
        url: str,
    ) -> dict:

        browser = BrowserCapture(
            self.output_dir,
        )

        try:
            await browser.start()

            # 1. Capture primary desktop viewport
            capture = await browser.capture(
                url,
            )

            # 2. Capture responsive viewports & differential rules
            if browser.context:
                multi_vp = MultiViewportCapture(self.output_dir)
                vp_results = await multi_vp.capture_all(browser.context, url)
                capture["viewports"] = vp_results.get("viewports", {})
                capture["responsive_rules"] = vp_results.get("responsive_rules", [])

            writer = SnapshotWriter(
                self.output_dir,
            )

            snapshot_dir = writer.write(
                capture,
            )

            capture["snapshot_dir"] = str(
                snapshot_dir
            )

            return capture

        finally:
            await browser.close()
