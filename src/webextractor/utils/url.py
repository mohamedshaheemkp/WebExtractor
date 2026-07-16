from urllib.parse import urljoin
from urllib.parse import urlparse


def normalize(url: str) -> str:
    return url.split("#")[0]


def domain(url: str) -> str:
    return urlparse(url).netloc


def filename(url: str) -> str:

    path = urlparse(url).path

    if path.endswith("/"):
        return "index.html"

    if "/" not in path:
        return path

    return path.split("/")[-1]


def extension(name: str) -> str:

    if "." not in name:
        return ""

    return name.rsplit(".", 1)[1].lower()


def path(url: str) -> str:
    return urlparse(url).path


def join(base: str, link: str) -> str:
    return urljoin(base, link)