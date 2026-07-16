from urllib.parse import urljoin
from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    return url.split("#")[0]


def domain(url: str) -> str:
    return urlparse(url).netloc


def join(base: str, link: str) -> str:
    return urljoin(base, link)