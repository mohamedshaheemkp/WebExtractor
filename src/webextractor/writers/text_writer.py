from pathlib import Path

from webextractor.models.asset import Asset
from webextractor.utils.filesystem import ensure_directory


def save_urls(
    assets: list[Asset],
    destination: Path,
) -> None:

    text = "\n".join(
        asset.url
        for asset in assets
    )

    ensure_directory(destination.parent)
    with destination.open("w", encoding="utf-8") as file:
        file.write(text)


def save_failed(
    failed: list[Asset],
    destination: Path,
) -> None:

    text = "\n".join(
        asset.url
        for asset in failed
    )

    ensure_directory(destination.parent)
    with destination.open("w", encoding="utf-8") as file:
        file.write(text)
