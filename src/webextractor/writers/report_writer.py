from __future__ import annotations

import json
from pathlib import Path

from webextractor.models.asset import Asset


def write_report(
    assets: list[Asset],
    output: Path,
) -> None:

    report = []

    for asset in assets:

        report.append(
            {
                "url": asset.url,
                "file": str(asset.local_path),
                "type": asset.asset_type.name,
                "mime": asset.mime_type,
                "size": asset.size,
                "status": asset.status_code,
                "downloaded": asset.downloaded,
            }
        )

    with (output / "report.json").open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            report,
            f,
            indent=4,
        )