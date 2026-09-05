from __future__ import annotations

from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class RouteAnalyzer:

    def analyze(
        self,
        html: str,
        base_url: str,
    ) -> list[str]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        base_domain = urlparse(
            base_url
        ).netloc

        routes = set()

        routes.add(
            urlparse(base_url).path or "/"
        )

        for link in soup.find_all("a"):

            href = link.get("href")

            if not href:
                continue

            absolute = urljoin(
                base_url,
                href,
            )

            parsed = urlparse(
                absolute
            )

            if parsed.netloc != base_domain:
                continue

            if parsed.scheme not in (
                "http",
                "https",
            ):
                continue

            routes.add(
                parsed.path or "/"
            )

        return sorted(routes)

    @classmethod
    def analyze_routes(cls, html: str, base_url: str):
        routes_list = cls().analyze(html, base_url)
        from webextractor.model.route import Route
        return [Route(path=r, url=f"{base_url.rstrip('/')}{r}" if r.startswith('/') else f"{base_url}/{r}", name="Home" if r in ("/", "") else r.strip("/").capitalize()) for r in routes_list]

