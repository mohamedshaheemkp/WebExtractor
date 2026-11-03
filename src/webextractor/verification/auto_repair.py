from __future__ import annotations

from pathlib import Path
from typing import Any
from rich.console import Console

from webextractor.model.site_ir import SiteIR
from webextractor.verification.spatial_comparator import LayoutViolation

console = Console(legacy_windows=False)


class LayoutAutoRepair:
    """Patches SiteIR data and injects programmatic layout corrections."""

    @classmethod
    def apply_repairs(
        cls,
        site_ir: SiteIR,
        violations: list[LayoutViolation],
        output_dir: Path
    ) -> bool:
        if not violations:
            return False

        css_overrides: list[str] = [
            "/* ───────────────────────────────────────────────────────────── */",
            "/* WebExtractor Automated Spatial Repair Overrides              */",
            "/* ───────────────────────────────────────────────────────────── */\n"
        ]

        modified = False

        for v in violations:
            if v.violation_type == "OVERLAY_COLLISION":
                role = v.details.get("role")
                rec_css = v.details.get("recommended_style")
                selector = f"[data-framer-name='{v.identifier}']" if v.identifier else v.target_element
                css_overrides.append(f"{selector} {{\n  {rec_css}\n}}\n")
                modified = True

            elif v.violation_type == "TRACK_CLAMPED":
                rec_css = v.details.get("recommended_style")
                selector = f"[data-framer-name='{v.identifier}']" if v.identifier else f".{v.identifier}"
                css_overrides.append(
                    f"{selector} {{\n  {rec_css}\n}}\n"
                    f"{selector} > * {{\n  flex-shrink: 0 !important;\n}}\n"
                )
                modified = True

            elif v.violation_type == "VIEWPORT_SHRINK":
                css_overrides.append(
                    "html, body, #root, #__next, main {\n"
                    "  width: 100% !important;\n"
                    "  min-height: 100vh !important;\n"
                    "  margin: 0 !important;\n"
                    "  padding: 0 !important;\n"
                    "  overflow-x: hidden !important;\n"
                    "}\n"
                )
                modified = True

            elif v.violation_type == "MEDIA_AUTOPLAY_MISSING":
                # Ensure video tags in IR metadata retain muted autoplay flags
                if hasattr(site_ir, "reusable_components") and site_ir.reusable_components:
                    for comp in site_ir.reusable_components:
                        if isinstance(comp, dict) and comp.get("tag") == "video":
                            comp.setdefault("attributes", {})
                            comp["attributes"]["autoPlay"] = True
                            comp["attributes"]["muted"] = True
                            comp["attributes"]["loop"] = True
                            comp["attributes"]["playsInline"] = True
                if hasattr(site_ir, "components") and site_ir.components:
                    for comp in site_ir.components:
                        if isinstance(comp, dict) and comp.get("tag") == "video":
                            comp.setdefault("attributes", {})
                            comp["attributes"]["autoPlay"] = True
                            comp["attributes"]["muted"] = True
                            comp["attributes"]["loop"] = True
                            comp["attributes"]["playsInline"] = True
                modified = True

        out_path = Path(output_dir)

        # Write layout_repairs.css into styles directory (Next.js)
        styles_dir = out_path / "styles"
        if not styles_dir.exists() and (out_path / "src" / "styles").exists():
            styles_dir = out_path / "src" / "styles"
        styles_dir.mkdir(parents=True, exist_ok=True)

        repair_css_path = styles_dir / "layout_repairs.css"
        with open(repair_css_path, "a", encoding="utf-8") as f:
            f.write("\n".join(css_overrides))

        # Inject import into layout/framer stylesheet
        framer_css_path = styles_dir / "framer.css"
        if framer_css_path.exists():
            content = framer_css_path.read_text(encoding="utf-8")
            if "@import './layout_repairs.css';" not in content:
                framer_css_path.write_text(f"@import './layout_repairs.css';\n" + content, encoding="utf-8")

        # Also support standalone static HTML output (css/styles.css)
        static_css_dir = out_path / "css"
        if static_css_dir.exists():
            static_repair = static_css_dir / "layout_repairs.css"
            with open(static_repair, "a", encoding="utf-8") as f:
                f.write("\n".join(css_overrides))
            static_styles = static_css_dir / "styles.css"
            if static_styles.exists():
                c_static = static_styles.read_text(encoding="utf-8")
                if "@import './layout_repairs.css';" not in c_static:
                    static_styles.write_text(f"@import './layout_repairs.css';\n" + c_static, encoding="utf-8")

        return modified

