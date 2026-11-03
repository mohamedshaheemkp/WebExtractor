Here is the complete implementation of the spatial tree comparison and automated repair system for src/webextractor/verification/.Architecture OverviewThe system operates across three core modules:spatial_tree.py: Runs in Playwright to extract normalized bounding boxes (x, y, width, height), computed display properties, z-index hierarchy, and positioning data for key structural nodes.spatial_comparator.py: Compares the original baseline spatial tree with the local reconstructed spatial tree to identify regressions (layer collisions, track clamping, viewport shrinkage, media attribute drops).auto_repair.py: Converts detected layout violations into programmatic repair patches on the SiteIR and re-emits the necessary CSS overrides and JSX attributes.File 1: src/webextractor/verification/spatial_tree.pyCreate this file to extract spatial coordinates and computed layout properties from any active Playwright page.Pythonfrom __future__ import annotations

from typing import Any
from playwright.async_api import Page


class SpatialTreeExtractor:
    """Extracts geometric bounding boxes and layout properties of key elements."""

    EXTRACT_SCRIPT = """() => {
        const selector = [
            'header', 'nav', 'footer', 'main', 'section',
            'video', 'canvas', '[data-framer-name]',
            '[class*="header"]', '[class*="nav"]', '[class*="footer"]',
            '[class*="carousel"]', '[class*="slider"]', '[class*="track"]'
        ].join(', ');

        const elements = Array.from(document.querySelectorAll(selector));
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        return elements.map((el, index) => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            
            // Collect identifiable attributes
            const framerName = el.getAttribute('data-framer-name') || '';
            const id = el.id || '';
            const className = typeof el.className === 'string' ? el.className : '';
            const tag = el.tagName.toLowerCase();

            return {
                index,
                tag,
                id,
                className,
                framerName,
                identifier: framerName || id || (className ? className.split(' ')[0] : `${tag}_${index}`),
                rect: {
                    top: Math.round(rect.top),
                    left: Math.round(rect.left),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    right: Math.round(rect.right),
                    bottom: Math.round(rect.bottom),
                },
                computed: {
                    position: style.position,
                    display: style.display,
                    flexDirection: style.flexDirection,
                    flexWrap: style.flexWrap,
                    overflow: style.overflow,
                    overflowX: style.overflowX,
                    zIndex: style.zIndex,
                    opacity: style.opacity,
                    visibility: style.visibility,
                    transform: style.transform
                },
                isMedia: tag === 'video' || tag === 'canvas',
                videoAttributes: tag === 'video' ? {
                    autoplay: el.hasAttribute('autoplay') || el.autoplay,
                    muted: el.hasAttribute('muted') || el.muted,
                    loop: el.hasAttribute('loop') || el.loop,
                    playsInline: el.hasAttribute('playsinline')
                } : null
            };
        }).filter(item => item.rect.width > 0 && item.rect.height > 0);
    }"""

    @classmethod
    async def capture(cls, page: Page) -> list[dict[str, Any]]:
        """Executes the spatial extraction inside the browser context."""
        return await page.evaluate(cls.EXTRACT_SCRIPT)
File 2: src/webextractor/verification/spatial_comparator.pyCreate this file to detect structural, collision, and track clamping regressions between the baseline and reconstructed pages.Pythonfrom __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LayoutViolation:
    violation_type: str  # 'OVERLAY_COLLISION', 'TRACK_CLAMPED', 'VIEWPORT_SHRINK', 'MEDIA_AUTOPLAY_MISSING'
    identifier: str
    target_element: str
    details: dict[str, Any]
    severity: str = "ERROR"  # 'WARNING' or 'ERROR'


class SpatialComparator:
    """Compares baseline vs reconstructed spatial trees and outputs actionable layout violations."""

    def __init__(self, baseline_nodes: list[dict[str, Any]], reconstructed_nodes: list[dict[str, Any]]):
        self.baseline_nodes = baseline_nodes
        self.reconstructed_nodes = reconstructed_nodes
        self._baseline_map = {n["identifier"]: n for n in baseline_nodes}
        self._reconstructed_map = {n["identifier"]: n for n in reconstructed_nodes}

    def compare(self) -> list[LayoutViolation]:
        violations: list[LayoutViolation] = []
        
        violations.extend(self._check_overlay_collisions())
        violations.extend(self._check_horizontal_tracks())
        violations.extend(self._check_viewport_shrinkage())
        violations.extend(self._check_media_autoplay())

        return violations

    def _check_overlay_collisions(self) -> list[LayoutViolation]:
        """Detects if navigation or footer elements collided into main content areas."""
        violations = []
        overlay_tags = {"header", "nav", "footer"}

        for r_node in self.reconstructed_nodes:
            is_overlay = r_node["tag"] in overlay_tags or "nav" in r_node["className"].lower() or "footer" in r_node["className"].lower()
            if not is_overlay:
                continue

            r_rect = r_node["rect"]
            b_node = self._baseline_map.get(r_node["identifier"])

            # Check if element was pinned/fixed at viewport boundary in baseline but shifted inside center in rebuild
            if b_node:
                b_rect = b_node["rect"]
                # Vertical anchoring drifted into the vertical center
                if b_rect["top"] < 100 and r_rect["top"] > 150:
                    violations.append(LayoutViolation(
                        violation_type="OVERLAY_COLLISION",
                        identifier=r_node["identifier"],
                        target_element=r_node["tag"],
                        details={
                            "role": "header",
                            "expected_top": b_rect["top"],
                            "actual_top": r_rect["top"],
                            "recommended_style": "position: fixed; top: 0; left: 0; width: 100%; z-index: 50;"
                        }
                    ))
                elif b_rect["bottom"] > 700 and r_rect["bottom"] < 600:
                    violations.append(LayoutViolation(
                        violation_type="OVERLAY_COLLISION",
                        identifier=r_node["identifier"],
                        target_element=r_node["tag"],
                        details={
                            "role": "footer",
                            "expected_bottom": b_rect["bottom"],
                            "actual_bottom": r_rect["bottom"],
                            "recommended_style": "position: fixed; bottom: 0; left: 0; width: 100%; z-index: 50;"
                        }
                    ))

        return violations

    def _check_horizontal_tracks(self) -> list[LayoutViolation]:
        """Detects horizontal carousel tracks that got clipped or lost their flex-row dimensions."""
        violations = []

        for b_id, b_node in self._baseline_map.items():
            # Check if this container held horizontal content extending beyond viewport width
            if b_node["rect"]["width"] > 1600 or "carousel" in b_node["className"].lower() or "track" in b_node["className"].lower():
                r_node = self._reconstructed_map.get(b_id)
                if r_node:
                    r_width = r_node["rect"]["width"]
                    # If reconstructed track collapsed to standard screen width or intrinsic card width
                    if r_width < (b_node["rect"]["width"] * 0.7):
                        violations.append(LayoutViolation(
                            violation_type="TRACK_CLAMPED",
                            identifier=b_id,
                            target_element=r_node["tag"],
                            details={
                                "baseline_width": b_node["rect"]["width"],
                                "reconstructed_width": r_width,
                                "recommended_style": "display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; width: max-content !important;"
                            }
                        ))

        return violations

    def _check_viewport_shrinkage(self) -> list[LayoutViolation]:
        """Detects if root containers or main sections collapsed into intrinsic boxes."""
        violations = []
        for r_node in self.reconstructed_nodes:
            if r_node["tag"] in {"main", "body"} or r_node["framerName"] == "Page":
                if r_node["rect"]["width"] < 1000:  # Collapsed into ~729px box
                    violations.append(LayoutViolation(
                        violation_type="VIEWPORT_SHRINK",
                        identifier=r_node["identifier"],
                        target_element=r_node["tag"],
                        details={
                            "actual_width": r_node["rect"]["width"],
                            "recommended_style": "width: 100vw; min-height: 100vh; overflow-x: hidden;"
                        }
                    ))
        return violations

    def _check_media_autoplay(self) -> list[LayoutViolation]:
        """Detects videos missing autoplay/muted/playsInline configurations."""
        violations = []
        for r_node in self.reconstructed_nodes:
            if r_node["tag"] == "video":
                attrs = r_node.get("videoAttributes") or {}
                if not (attrs.get("autoplay") and attrs.get("muted") and attrs.get("playsInline")):
                    violations.append(LayoutViolation(
                        violation_type="MEDIA_AUTOPLAY_MISSING",
                        identifier=r_node["identifier"],
                        target_element="video",
                        details={
                            "attributes": attrs,
                            "required": ["autoPlay", "muted", "loop", "playsInline"]
                        }
                    ))
        return violations
File 3: src/webextractor/verification/auto_repair.pyCreate this file to apply repairs to SiteIR and emit an override stylesheet (layout_repairs.css).   Pythonfrom __future__ import annotations

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
                if hasattr(site_ir, "reusable_components"):
                    for comp in site_ir.reusable_components:
                        if comp.get("tag") == "video":
                            comp.setdefault("attributes", {})
                            comp["attributes"]["autoPlay"] = True
                            comp["attributes"]["muted"] = True
                            comp["attributes"]["loop"] = True
                            comp["attributes"]["playsInline"] = True
                modified = True

        # Write layout_repairs.css into styles directory
        styles_dir = output_dir / "styles"
        if not styles_dir.exists():
            styles_dir = output_dir / "src" / "styles"
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

        return modified
File 4: Expose Modules in src/webextractor/verification/__init__.pyUpdate src/webextractor/verification/__init__.py to export the new classes:   Pythonfrom webextractor.verification.report import VerificationReport
from webextractor.verification.screenshots import ScreenshotComparator
from webextractor.verification.visual_diff import VisualDiffScorer
from webextractor.verification.spatial_tree import SpatialTreeExtractor
from webextractor.verification.spatial_comparator import SpatialComparator, LayoutViolation
from webextractor.verification.auto_repair import LayoutAutoRepair

__all__ = [
    "VerificationReport",
    "ScreenshotComparator",
    "VisualDiffScorer",
    "SpatialTreeExtractor",
    "SpatialComparator",
    "LayoutViolation",
    "LayoutAutoRepair",
]
Step 5: Wire the Self-Correction Loop into src/webextractor/cli/commands/rip.pyIn src/webextractor/cli/commands/rip.py, import the modules and call the verification/repair loop right after the initial generation pass:   Python# Add imports at top of rip.py:
from webextractor.verification.spatial_tree import SpatialTreeExtractor
from webextractor.verification.spatial_comparator import SpatialComparator
from webextractor.verification.auto_repair import LayoutAutoRepair
Then, integrate the comparative step right after browser capture and code generation:   Python    # ── [Stage 1: Capture baseline spatial tree from live site] ──
    console.print("\n[bold cyan][1/6] Capturing baseline geometry & spatial tree...[/bold cyan]")
    # Using existing crawler browser context:
    baseline_spatial_tree = await SpatialTreeExtractor.capture(crawler.page)

    # ... [Assets, Analysis, and Generation stages execute as normal] ...

    # ── [Stage 6: Automated Verification & Auto-Repair Pass] ──
    console.print("\n[bold cyan][6/6] Verifying layout fidelity & auto-repairing...[/bold cyan]")
    
    # Run a local headless check on the generated static/React output
    # (Using crawler's playwright instance to inspect generated output or local server)
    try:
        test_page = await crawler.browser.new_page()
        local_entry = output_dir / "index.html"
        
        if local_entry.exists():
            await test_page.goto(f"file://{local_entry.resolve()}")
            await test_page.wait_for_load_state("networkidle")
            
            reconstructed_spatial_tree = await SpatialTreeExtractor.capture(test_page)
            
            # Run comparison
            comparator = SpatialComparator(baseline_spatial_tree, reconstructed_spatial_tree)
            violations = comparator.compare()
            
            if violations:
                console.print(f"[yellow]⚠ Found {len(violations)} layout regressions. Applying auto-repairs...[/yellow]")
                repaired = LayoutAutoRepair.apply_repairs(site_ir, violations, output_dir)
                if repaired:
                    console.print("[green]✓ Applied layout_repairs.css patches and un-clamped carousel tracks.[/green]")
            else:
                console.print("[green]✓ Spatial geometry verified with 0 layout regressions.[/green]")
                
        await test_page.close()
    except Exception as e:
        console.print(f"[dim]Note: Local headless verification skipped: {e}[/dim]")
Testing the FixOnce these files are in place, test the pipeline: