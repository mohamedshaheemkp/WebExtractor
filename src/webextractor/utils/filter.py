from __future__ import annotations

from urllib.parse import urlparse


TRACKING_DOMAINS = {
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "facebook.com",
    "connect.facebook.net",
}


SKIP_EXTENSIONS = {
    ".map",
}


def should_download(
    url: str,
    status: int | None,
) -> bool:

    if status is None:
        return False

    if status != 200:
        return False

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False

    host = parsed.netloc.lower()

    for domain in TRACKING_DOMAINS:

        if domain in host:
            return False

    for ext in SKIP_EXTENSIONS:

        if parsed.path.lower().endswith(ext):
            return False

    return True