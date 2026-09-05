from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class SiteModel:

    url: str
    title: str | None

    dom: dict[str, Any]

    assets: dict[str, Any]

    routes: list[str]

    network: list[dict[str, Any]]

    components: dict[str, Any] | None = None

    repeated_components: dict[str, Any] | None = None

    tokens: dict[str, Any] | None = None

    screenshot: str | None = None

    def save(
        self,
        path: str | Path,
    ) -> None:

        path = Path(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                asdict(self),
                indent=2,
            ),
            encoding="utf-8",
        )
