from __future__ import annotations

from typing import Any
from bs4 import BeautifulSoup


class DOMAnalyzer:

    def analyze(
        self,
        html: str,
    ) -> dict[str, Any]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        return {
            "title": self._title(soup),
            "headings": self._headings(soup),
            "links": self._links(soup),
            "images": self._images(soup),
            "sections": self._sections(soup),
            "forms": self._forms(soup),
            "buttons": self._buttons(soup),
            "semantic_tree": self._semantic_tree(soup),
        }

    def _title(self, soup):
        if soup.title:
            return soup.title.get_text(
                strip=True
            )

        return None

    def _headings(self, soup):

        result = []

        for tag in soup.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6"]
        ):
            result.append(
                {
                    "level": tag.name,
                    "text": tag.get_text(
                        " ",
                        strip=True,
                    ),
                }
            )

        return result

    def _links(self, soup):

        result = []

        for tag in soup.find_all("a"):

            href = tag.get("href")

            if not href:
                continue

            result.append(
                {
                    "text": tag.get_text(
                        " ",
                        strip=True,
                    ),
                    "href": href,
                }
            )

        return result

    def _images(self, soup):

        result = []

        for tag in soup.find_all("img"):

            result.append(
                {
                    "src": tag.get("src"),
                    "alt": tag.get("alt"),
                    "width": tag.get("width"),
                    "height": tag.get("height"),
                }
            )

        return result

    def _sections(self, soup):

        sections = []

        for tag in soup.find_all(
            ["header", "nav", "main", "section", "article", "footer"]
        ):

            text = tag.get_text(
                " ",
                strip=True,
            )

            sections.append(
                {
                    "element": tag.name,
                    "id": tag.get("id"),
                    "class": tag.get("class"),
                    "text_preview": text[:200],
                }
            )

        return sections

    def _forms(self, soup):

        return [
            {
                "action": form.get("action"),
                "method": form.get("method"),
            }
            for form in soup.find_all("form")
        ]

    def _buttons(self, soup):

        return [
            button.get_text(
                " ",
                strip=True,
            )
            for button in soup.find_all(
                ["button"]
            )
        ]

    def _semantic_tree(self, soup):

        root = soup.body

        if root is None:
            return {}

        return self._build_node(
            root,
            depth=0,
        )

    def _build_node(
        self,
        element,
        depth: int,
    ):

        if depth > 8:
            return None

        children = []

        for child in element.find_all(
            recursive=False
        ):

            if not getattr(
                child,
                "name",
                None,
            ):
                continue

            node = self._build_node(
                child,
                depth + 1,
            )

            if node:
                children.append(node)

        return {
            "tag": element.name,
            "id": element.get("id"),
            "classes": element.get("class", []),
            "children": children,
        }
