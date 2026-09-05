from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class HARParser:
    """Parser for HTTP Archive (.har) files."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    def parse(self) -> dict[str, Any]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"HAR file not found: {self.file_path}")

        with self.file_path.open("r", encoding="utf-8", errors="ignore") as f:
            return json.load(f)

    def get_entries(self) -> list[dict[str, Any]]:
        data = self.parse()
        return data.get("log", {}).get("entries", [])

    def get_pages(self) -> list[dict[str, Any]]:
        data = self.parse()
        return data.get("log", {}).get("pages", [])
