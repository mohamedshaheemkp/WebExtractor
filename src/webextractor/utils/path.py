from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlparse

from webextractor.utils.sanitize import filename


def build_output_path(
    url: str,
    output: Path,
) -> Path:

    parsed = urlparse(url)

    host = parsed.netloc

    path = parsed.path.strip("/")

    if not path:

        path = "index.html"

    if path.endswith("/"):

        path += "index.html"

    path = filename(path)

    final = output / host / path

    if parsed.query:

        queries = parse_qs(parsed.query)

        if queries:

            stem = final.stem

            suffix = final.suffix

            key = "_".join(
                sorted(queries.keys())
            )

            final = final.with_name(
                f"{stem}_{key}{suffix}"
            )

    return final