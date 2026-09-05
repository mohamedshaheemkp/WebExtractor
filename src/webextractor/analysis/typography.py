from __future__ import annotations

import re
from webextractor.model.token import TypographyToken


class TypographyAnalyzer:
    """Analyzes typography scales and font hierarchies."""

    @staticmethod
    def analyze(css_content: str) -> list[TypographyToken]:
        font_sizes = re.findall(r"font-size\s*:\s*([^;]+);", css_content, re.IGNORECASE)
        font_weights = re.findall(r"font-weight\s*:\s*([^;]+);", css_content, re.IGNORECASE)

        clean_sizes = sorted(list(set(s.strip() for s in font_sizes)))[:6]
        tokens = []
        for idx, sz in enumerate(clean_sizes):
            tokens.append(
                TypographyToken(
                    name=f"text-scale-{idx + 1}",
                    font_family="Inter, system-ui, sans-serif",
                    font_size=sz,
                    font_weight=font_weights[idx].strip() if idx < len(font_weights) else "400",
                )
            )
        return tokens
