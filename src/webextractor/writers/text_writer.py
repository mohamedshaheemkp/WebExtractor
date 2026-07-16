from __future__ import annotations

from pathlib import Path

from webextractor.models.asset import Asset
from webextractor.utils.filesystem import ensure_parent


def write_urls(
    assets: list[Asset],
    output: Path,
) -> None:

    ensure_parent(output / "urls.txt")

    with (output / "urls.txt").open(
        "w",
        encoding="utf-8",
    ) as file:

        for asset in assets:
            file.write(asset.url + "\n")


def write_failed(
    failed: list[Asset],
    output: Path,
) -> None:

    ensure_parent(output / "failed.txt")

    with (output / "failed.txt").open(
        "w",
        encoding="utf-8",
    ) as file:

        for asset in failed:
            file.write(asset.url + "\n")