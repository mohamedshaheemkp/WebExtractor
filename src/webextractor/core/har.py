from __future__ import annotations

import json
from pathlib import Path


class HARReader:

    def __init__(self, file: str | Path) -> None:
        self.file = Path(file)

    def load(self) -> dict:

        with self.file.open(
            "r",
            encoding="utf-8",
            errors="ignore",
        ) as f:

            return json.load(f)

    def entries(self) -> list[dict]:

        data = self.load()

        return data.get("log", {}).get("entries", [])