from __future__ import annotations

from urllib.parse import urljoin
from bs4 import BeautifulSoup


class AssetAnalyzer:

    def analyze(
        self,
        html: str,
        base_url: str,
    ) -> dict:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        images = []
        videos = []
        fonts = []
        stylesheets = []
        scripts = []

        for tag in soup.find_all("img"):

            src = tag.get("src")

            if src:
                images.append(
                    urljoin(
                        base_url,
                        src,
                    )
                )

        for tag in soup.find_all("video"):

            src = tag.get("src")

            if src:
                videos.append(
                    urljoin(
                        base_url,
                        src,
                    )
                )

        for tag in soup.find_all("link"):

            href = tag.get("href")

            if not href:
                continue

            rel = tag.get(
                "rel",
                [],
            )

            if "stylesheet" in rel:
                stylesheets.append(
                    urljoin(
                        base_url,
                        href,
                    )
                )

            if "font" in str(rel).lower():
                fonts.append(
                    urljoin(
                        base_url,
                        href,
                    )
                )

        for tag in soup.find_all("script"):

            src = tag.get("src")

            if src:
                scripts.append(
                    urljoin(
                        base_url,
                        src,
                    )
                )

        return {
            "images": list(dict.fromkeys(images)),
            "videos": list(dict.fromkeys(videos)),
            "fonts": list(dict.fromkeys(fonts)),
            "stylesheets": list(
                dict.fromkeys(stylesheets)
            ),
            "scripts": list(
                dict.fromkeys(scripts)
            ),
        }
