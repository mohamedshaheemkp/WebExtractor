from __future__ import annotations

import json
from pathlib import Path

from webextractor.model.asset import Asset


def write_reports(assets: list[Asset], output_dir: Path) -> None:
    """Generate report.json, urls.txt, failed.txt, and tree.txt in output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. report.json
    report_data = [
        {
            "url": asset.url,
            "domain": asset.domain,
            "filename": asset.filename,
            "type": asset.asset_type.value,
            "mime_type": asset.mime_type,
            "status_code": asset.status_code,
            "size": asset.size,
            "downloaded": asset.downloaded,
            "local_path": str(asset.local_path.relative_to(output_dir)) if asset.local_path and asset.local_path.is_relative_to(output_dir) else str(asset.local_path),
        }
        for asset in assets
    ]
    with (output_dir / "report.json").open("w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    # 2. urls.txt
    with (output_dir / "urls.txt").open("w", encoding="utf-8") as f:
        for asset in assets:
            f.write(f"{asset.url}\n")

    # 3. failed.txt
    with (output_dir / "failed.txt").open("w", encoding="utf-8") as f:
        for asset in assets:
            if not asset.downloaded:
                f.write(f"{asset.url}\n")

    # 4. tree.txt
    tree_lines = []
    for path in sorted(output_dir.rglob("*")):
        if path.name in ("report.json", "urls.txt", "failed.txt", "tree.txt"):
            continue
        rel = path.relative_to(output_dir)
        indent = "    " * (len(rel.parts) - 1)
        tree_lines.append(f"{indent}{path.name}")

    with (output_dir / "tree.txt").open("w", encoding="utf-8") as f:
        f.write("\n".join(tree_lines))
