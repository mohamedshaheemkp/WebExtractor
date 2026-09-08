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

        # Multi-page route persistence
        pages = capture.get("pages", [])
        manifest_entries = []

        if pages:
            routes_dir = snapshot_dir / "routes"
            routes_dir.mkdir(parents=True, exist_ok=True)

            for p in pages:
                route = p.get("route", "/")
                slug = p.get("slug") or ("root" if route == "/" else route.strip("/").replace("/", "_"))
                page_dir = routes_dir / slug
                page_dir.mkdir(parents=True, exist_ok=True)

                if p.get("html"):
                    (page_dir / "page.html").write_text(p["html"], encoding="utf-8")

                if p.get("requests") is not None:
                    (page_dir / "network.json").write_text(
                        json.dumps(p["requests"], indent=2),
                        encoding="utf-8",
                    )

                if p.get("dom"):
                    (page_dir / "dom.json").write_text(
                        json.dumps(p["dom"], indent=2),
                        encoding="utf-8",
                    )

                page_meta = {
                    "route": route,
                    "url": p.get("url"),
                    "title": p.get("title"),
                    "screenshot": p.get("screenshot"),
                    "request_count": len(p.get("requests", [])),
                }
                (page_dir / "metadata.json").write_text(
                    json.dumps(page_meta, indent=2),
                    encoding="utf-8",
                )

                manifest_entries.append({
                    "route": route,
                    "slug": slug,
                    "url": p.get("url"),
                    "title": p.get("title"),
                    "screenshot": p.get("screenshot"),
                    "path": f"routes/{slug}",
                })

            (snapshot_dir / "routes_manifest.json").write_text(
                json.dumps(
                    {
                        "url": capture.get("url"),
                        "total_routes": len(manifest_entries),
                        "routes": manifest_entries,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        return snapshot_dir
