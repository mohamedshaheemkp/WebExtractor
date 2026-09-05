from __future__ import annotations

from bs4 import BeautifulSoup


class AccessibilityAnalyzer:
    """Analyzes semantic landmarks and accessibility metrics."""

    @staticmethod
    def analyze(html_content: str) -> dict[str, int]:
        soup = BeautifulSoup(html_content, "lxml")
        return {
            "h1_count": len(soup.find_all("h1")),
            "h2_count": len(soup.find_all("h2")),
            "nav_count": len(soup.find_all("nav")),
            "main_count": len(soup.find_all("main")),
            "aria_labels": len(soup.find_all(attrs={"aria-label": True})),
            "images_with_alt": len(soup.find_all("img", alt=True)),
            "images_total": len(soup.find_all("img")),
        }
