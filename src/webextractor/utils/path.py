from pathlib import Path
from urllib.parse import urlparse

from webextractor.utils.sanitize import filename


def url_to_path(url: str, output: Path) -> Path:

    parsed = urlparse(url)

    host = parsed.netloc

    path = parsed.path.strip("/")

    if not path:
        path = "index.html"

    return output / host / filename(path)