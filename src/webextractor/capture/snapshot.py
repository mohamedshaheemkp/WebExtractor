from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SnapshotWriter:

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)

    def write(
        self,
        capture: dict[str, Any],
    ) -> Path:

        snapshot_dir = self.output_dir / "snapshot"

        snapshot_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        html_path = snapshot_dir / "page.html"

        html_path.write_text(
            capture["html"],
            encoding="utf-8",
        )

        metadata = {
            "url": capture["url"],
            "title": capture["title"],
            "screenshot": capture["screenshot"],
            "viewport": capture["viewport"],
            "request_count": len(
                capture["requests"]
            ),
        }

        metadata_path = (
            snapshot_dir / "metadata.json"
        )

        metadata_path.write_text(
            json.dumps(
                metadata,
                indent=2,
            ),
            encoding="utf-8",
        )

        requests_path = (
            snapshot_dir / "network.json"
        )

        requests_path.write_text(
            json.dumps(
                capture["requests"],
                indent=2,
            ),
            encoding="utf-8",
        )

        return snapshot_dir
