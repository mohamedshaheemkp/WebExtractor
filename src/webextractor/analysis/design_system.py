from __future__ import annotations

import re
from typing import Any


def rgb_to_hex(rgb_str: str) -> str:
    """Convert rgb(r, g, b) or rgba(r, g, b, 1) to #RRGGBB."""
    match = re.search(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)", rgb_str)
    if not match:
        return rgb_str

    r, g, b = int(match.group(1)), int(match.group(2)), int(match.group(3))
    alpha = match.group(4)

    if alpha is not None and float(alpha) < 0.99:
        # Keep rgba format if transparent
        return f"rgba({r}, {g}, {b}, {float(alpha):.2g})"

    return f"#{r:02X}{g:02X}{b:02X}"


def luminance(hex_or_rgb: str) -> float:
    """Calculates relative brightness (0.0 to 1.0)."""
    match = re.search(r"#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})", hex_or_rgb)
    if match:
        r, g, b = int(match.group(1), 16), int(match.group(2), 16), int(match.group(3), 16)
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

    match_rgb = re.search(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", hex_or_rgb)
    if match_rgb:
        r, g, b = int(match_rgb.group(1)), int(match_rgb.group(2)), int(match_rgb.group(3))
        return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

    return 0.5


class DesignSystemInferrer:
    """
    Transforms raw observed CSS tokens into a clean, normalized,
    and semantically inferred Design System.
    """

    def infer(self, raw_tokens: dict[str, Any]) -> dict[str, Any]:
        return {
            "colors": self._infer_colors(raw_tokens.get("colors", [])),
            "typography": self._infer_typography(raw_tokens.get("typography", {})),
            "radii": self._infer_radii(raw_tokens.get("radii", [])),
            "spacing": self._infer_spacing(raw_tokens.get("spacing", {})),
            "layout": raw_tokens.get("layout", {}),
        }

    def _infer_colors(self, raw_colors: list[dict[str, Any]]) -> dict[str, str]:
        # Filter out purely transparent colors and default browser link blues
        valid_colors = []
        for c in raw_colors:
            val = c["value"]
            if val in ("rgba(0, 0, 0, 0)", "transparent", "rgb(0, 0, 238)"):
                continue
            valid_colors.append((rgb_to_hex(val), c["usage"]))

        if not valid_colors:
            return {
                "background": "#000000",
                "surface": "#0A0A0A",
                "surfaceElevated": "#161616",
                "foreground": "#FFFFFF",
                "muted": "rgba(255, 255, 255, 0.6)",
                "accent": "#FF462E",
            }

        # Deduplicate while preserving order of usage
        unique_colors = []
        seen = set()
        for hex_val, usage in valid_colors:
            if hex_val not in seen:
                seen.add(hex_val)
                unique_colors.append((hex_val, usage))

        colors_by_lum = sorted(unique_colors, key=lambda x: luminance(x[0]))

        # Darkest color -> background
        dark_colors = [c[0] for c in colors_by_lum if luminance(c[0]) < 0.2]
        light_colors = [c[0] for c in colors_by_lum if luminance(c[0]) > 0.8]
        mid_colors = [c[0] for c in colors_by_lum if 0.2 <= luminance(c[0]) <= 0.8]

        background = dark_colors[0] if dark_colors else "#000000"
        surface = dark_colors[1] if len(dark_colors) > 1 else (dark_colors[0] if dark_colors else "#0A0A0A")
        surface_elevated = dark_colors[2] if len(dark_colors) > 2 else (dark_colors[1] if len(dark_colors) > 1 else "#161616")

        foreground = light_colors[-1] if light_colors else "#FFFFFF"
        muted = "rgba(255, 255, 255, 0.6)"
        for c in unique_colors:
            if "rgba" in c[0] or (0.4 < luminance(c[0]) < 0.75 and c[0] != foreground):
                muted = c[0]
                break

        # Accent: Distinctive color (high chroma / non-grayscale)
        accent = "#FF462E"
        for c, _ in unique_colors:
            match = re.search(r"#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})", c)
            if match:
                r, g, b = int(match.group(1), 16), int(match.group(2), 16), int(match.group(3), 16)
                # Check for saturation / colorfulness
                if max(r, g, b) - min(r, g, b) > 40:
                    accent = c
                    break

        return {
            "background": background,
            "surface": surface,
            "surfaceElevated": surface_elevated,
            "foreground": foreground,
            "muted": muted,
            "accent": accent,
        }

    def _infer_typography(self, raw_typo: dict[str, Any]) -> dict[str, Any]:
        families = [f["value"] for f in raw_typo.get("families", [])]
        weights = [int(w["value"]) for w in raw_typo.get("weights", []) if str(w["value"]).isdigit()]

        display_family = "Clash Display, sans-serif"
        body_family = "Inter, sans-serif"

        for fam in families:
            clean = fam.replace('"', "").replace("'", "")
            if any(k in clean.lower() for k in ("clash", "display", "grotesk", "syne", "monument", "heading")):
                display_family = fam
            elif any(k in clean.lower() for k in ("inter", "roboto", "geist", "helvetica", "sans")):
                body_family = fam

        # Parse and sort sizes
        raw_sizes = raw_typo.get("sizes", [])
        numeric_sizes = []
        for s in raw_sizes:
            match = re.search(r"([\d.]+)px", str(s["value"]))
            if match:
                numeric_sizes.append(float(match.group(1)))

        sorted_sizes = sorted(set(numeric_sizes))
        
        # Categorize sizes into semantic scale
        size_scale = {}
        if sorted_sizes:
            labels = ["xs", "sm", "md", "lg", "xl", "display", "displayLarge"]
            if len(sorted_sizes) >= len(labels):
                # Pick 7 representative steps
                step = len(sorted_sizes) / len(labels)
                for i, label in enumerate(labels):
                    val = sorted_sizes[min(int(i * step), len(sorted_sizes) - 1)]
                    size_scale[label] = f"{int(val)}px"
            else:
                for i, val in enumerate(sorted_sizes):
                    lbl = labels[i] if i < len(labels) else f"size_{i+1}"
                    size_scale[lbl] = f"{int(val)}px"
        else:
            size_scale = {
                "xs": "12px",
                "sm": "18px",
                "md": "24px",
                "lg": "34px",
                "xl": "48px",
                "display": "90px",
                "displayLarge": "120px",
            }

        return {
            "display": {
                "family": display_family,
                "weights": sorted(weights) if weights else [400, 500, 600],
            },
            "body": {
                "family": body_family,
                "weights": [400, 500],
            },
            "sizes": size_scale,
        }

    def _infer_radii(self, raw_radii: list[dict[str, Any]]) -> dict[str, str]:
        radii_values = []
        for r in raw_radii:
            val = str(r.get("value", ""))
            match = re.search(r"(\d+)px", val)
            if match and int(match.group(1)) > 0:
                radii_values.append(int(match.group(1)))

        sorted_radii = sorted(set(radii_values))
        scale = {}

        if not sorted_radii:
            return {
                "card": "10px",
                "button": "13px",
                "container": "20px",
                "pill": "100px",
            }

        # Match smallest positive radii to card / button
        if len(sorted_radii) >= 1:
            scale["card"] = f"{sorted_radii[0]}px"
        if len(sorted_radii) >= 2:
            scale["button"] = f"{sorted_radii[1]}px"
        else:
            scale["button"] = scale["card"]

        if len(sorted_radii) >= 3:
            scale["container"] = f"{sorted_radii[2]}px"
        else:
            scale["container"] = "20px"

        large_radii = [r for r in sorted_radii if r >= 50]
        if large_radii:
            scale["pill"] = f"{large_radii[-1]}px"
        else:
            scale["pill"] = "100px"

        return scale

    def _infer_spacing(self, raw_spacing: dict[str, Any]) -> dict[str, str]:
        return {
            "xs": "4px",
            "sm": "8px",
            "md": "16px",
            "lg": "24px",
            "xl": "32px",
            "section": "100px",
        }
