from __future__ import annotations

from collections import Counter

from webextractor.models.asset import Asset
from webextractor.models.asset import AssetType


class AssetManager:

    def __init__(self) -> None:
        self._assets: dict[str, Asset] = {}

    def add(self, asset: Asset) -> None:

        if asset.url not in self._assets:
            self._assets[asset.url] = asset

    def get(self, url: str) -> Asset | None:
        return self._assets.get(url)

    def exists(self, url: str) -> bool:
        return url in self._assets

    @property
    def assets(self) -> list[Asset]:
        return list(self._assets.values())

    @property
    def count(self) -> int:
        return len(self._assets)

    def statistics(self) -> dict[AssetType, int]:

        counter = Counter(asset.asset_type for asset in self._assets.values())

        return dict(counter)