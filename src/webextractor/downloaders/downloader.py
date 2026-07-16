from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
)

from webextractor.models.asset import Asset
from webextractor.models.result import Result
from webextractor.utils.filesystem import ensure_parent


TIMEOUT = 20
MAX_WORKERS = 8


def download_asset(asset: Asset, output_dir: Path):

    destination = asset.local_path

    try:

        response = requests.get(
            asset.url,
            timeout=TIMEOUT,
            headers={
                "User-Agent":
                "Mozilla/5.0 WebExtractor"
            },
        )

        response.raise_for_status()

        ensure_parent(destination)
        with destination.open("wb") as file:
            file.write(response.content)

        return True, asset

    except Exception:

        return False, asset


def download_assets(
    assets: list[Asset],
    output_dir: Path,
) -> Result:

    result = Result()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
    ) as progress:

        task = progress.add_task(
            "Downloading",
            total=len(assets),
        )

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as executor:

            futures = [
                executor.submit(
                    download_asset,
                    asset,
                    output_dir,
                )
                for asset in assets
            ]

            for future in as_completed(futures):

                success, asset = future.result()

                if success:
                    asset.downloaded = True
                    result.success.append(asset)
                else:
                    result.failed.append(asset)

                progress.update(task, advance=1)

    return result