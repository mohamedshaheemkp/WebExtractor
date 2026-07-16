from __future__ import annotations

from pathlib import Path

from webextractor.config import config
from webextractor.models.asset import Asset
from webextractor.utils.filesystem import ensure_parent
from webextractor.utils.path import build_output_path


class Mirror:

    def prepare(self, asset: Asset) -> Path:

        path = build_output_path(
            asset.url,
            config.output_dir,
        )

        ensure_parent(path)

        asset.local_path = path

        return path

    def prepare_many(
        self,
        assets: list[Asset],
    ) -> None:

        for asset in assets:
            self.prepare(asset)