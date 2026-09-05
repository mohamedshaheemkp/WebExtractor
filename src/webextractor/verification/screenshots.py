from __future__ import annotations

from pathlib import Path


class ScreenshotComparator:
    """Handles comparison and verification of screenshot evidence."""

    @staticmethod
    def verify_paths(original: Path | None, generated: Path | None) -> bool:
        if original and original.exists() and generated and generated.exists():
            return True
        return False
