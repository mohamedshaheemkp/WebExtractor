from urllib.parse import urlparse


def valid_url(url: str) -> bool:

    parsed = urlparse(url)

    return bool(parsed.scheme and parsed.netloc)