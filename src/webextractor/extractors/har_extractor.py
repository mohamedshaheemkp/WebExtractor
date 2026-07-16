import json
from pathlib import Path


def load_har(path: Path) -> list[dict]:
    """
    Load HAR file and return all entries.
    """

    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(
        "r",
        encoding="utf-8",
        errors="ignore",
    ) as file:

        data = json.load(file)

    return data["log"]["entries"]
