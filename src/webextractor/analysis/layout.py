from __future__ import annotations

import re


class LayoutAnalyzer:
    """Analyzes layout systems (flex, grid, max-width containers, breakpoints)."""

    @staticmethod
    def analyze(css_content: str) -> dict[str, list[str]]:
        media_queries = re.findall(r"@media\s*\([^\)]+\)", css_content)
        flex_patterns = re.findall(r"display\s*:\s*flex;", css_content, re.IGNORECASE)
        grid_patterns = re.findall(r"display\s*:\s*grid;", css_content, re.IGNORECASE)

        return {
            "breakpoints": list(set(media_queries))[:5],
            "uses_flex": len(flex_patterns) > 0,
            "uses_grid": len(grid_patterns) > 0,
            "flex_count": len(flex_patterns),
            "grid_count": len(grid_patterns),
        }
