from __future__ import annotations

import re


class ReactSyntaxEmitter:
    """Helper to emit clean, formatted React TypeScript JSX code."""

    @staticmethod
    def escape_text(text: str) -> str:
        """Escapes text for safe inclusion in JSX."""
        return (
            text.replace("{", "&#123;")
            .replace("}", "&#125;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    @staticmethod
    def sanitize_identifier(name: str) -> str:
        """Sanitizes a string into a valid PascalCase React component identifier."""
        cleaned = re.sub(r"[^a-zA-Z0-9_]", " ", name)
        words = cleaned.split()
        if not words:
            return "Component"
        return "".join(w.capitalize() for w in words)
