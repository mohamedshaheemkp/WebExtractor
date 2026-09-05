from __future__ import annotations

from pathlib import Path
from typing import Any


class ScreenshotCapture:
    """Captures viewport and full-page screenshots."""

    @staticmethod
    async def capture_full_page(page: Any, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(output_path), full_page=True)
        return output_path

    @staticmethod
    async def capture_viewport(page: Any, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(output_path), full_page=False)
        return output_path
