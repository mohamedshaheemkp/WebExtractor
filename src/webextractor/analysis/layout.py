from __future__ import annotations

import re


class LayoutAnalyzer:
    """Analyzes layout systems (flex, grid, max-width containers, breakpoints)."""

    @staticmethod
    def analyze(css_content: str) -> dict[str, Any]:
        media_queries = re.findall(r"@media[^{]+", css_content)
        media_queries = [mq.strip() for mq in media_queries]
        flex_patterns = re.findall(r"display\s*:\s*flex;", css_content, re.IGNORECASE)
        grid_patterns = re.findall(r"display\s*:\s*grid;", css_content, re.IGNORECASE)

        # Infer breakpoint pixel thresholds from media queries
        bp_matches = re.findall(r"(?:min|max)-width\s*:\s*(\d+(?:\.\d+)?)\s*px", css_content, re.IGNORECASE)
        inferred_bps = sorted(list({int(float(m)) for m in bp_matches}), reverse=True)

        return {
            "breakpoints": list(dict.fromkeys(media_queries))[:10],
            "inferred_breakpoints": inferred_bps,
            "uses_flex": len(flex_patterns) > 0,
            "uses_grid": len(grid_patterns) > 0,
            "flex_count": len(flex_patterns),
            "grid_count": len(grid_patterns),
        }
