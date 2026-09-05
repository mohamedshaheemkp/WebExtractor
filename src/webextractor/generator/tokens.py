from __future__ import annotations

from pathlib import Path


class TokenCSSGenerator:
    """
    Generates structured, semantic CSS variables from an inferred Design System.
    """

    def generate(
        self,
        design_system: dict,
        output: str | Path,
    ) -> None:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            ":root {"
        ]

        # 1. Colors
        colors = design_system.get("colors", {})
        if isinstance(colors, dict) and colors:
            lines.append("  /* Colors */")
            for name, val in colors.items():
                lines.append(f"  --color-{name}: {val};")
        elif isinstance(colors, list) and colors:
            lines.append("  /* Colors */")
            for index, item in enumerate(colors[:20]):
                val = item.get("value") if isinstance(item, dict) else str(item)
                lines.append(f"  --color-{index + 1}: {val};")

        # 2. Typography
        typo = design_system.get("typography", {})
        if isinstance(typo, dict) and typo:
            lines.append("")
            lines.append("  /* Typography */")
            if "display" in typo and isinstance(typo["display"], dict):
                lines.append(f"  --font-display: {typo['display'].get('family', 'sans-serif')};")
            if "body" in typo and isinstance(typo["body"], dict):
                lines.append(f"  --font-body: {typo['body'].get('family', 'sans-serif')};")

            sizes = typo.get("sizes", {})
            if isinstance(sizes, dict):
                for name, val in sizes.items():
                    lines.append(f"  --font-size-{name}: {val};")
            elif isinstance(sizes, list):
                for index, item in enumerate(sizes[:15]):
                    val = item.get("value") if isinstance(item, dict) else str(item)
                    lines.append(f"  --font-size-{index + 1}: {val};")

        # 3. Radii
        radii = design_system.get("radii", {})
        if isinstance(radii, dict) and radii:
            lines.append("")
            lines.append("  /* Radii */")
            for name, val in radii.items():
                lines.append(f"  --radius-{name}: {val};")
        elif isinstance(radii, list) and radii:
            lines.append("")
            lines.append("  /* Radii */")
            for index, item in enumerate(radii[:10]):
                val = item.get("value") if isinstance(item, dict) else str(item)
                lines.append(f"  --radius-{index + 1}: {val};")

        # 4. Spacing
        spacing = design_system.get("spacing", {})
        if isinstance(spacing, dict) and spacing:
            lines.append("")
            lines.append("  /* Spacing */")
            for name, val in spacing.items():
                if isinstance(val, (str, int)):
                    lines.append(f"  --space-{name}: {val};")

        lines.append("}")

        output.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )
