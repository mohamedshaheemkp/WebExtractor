from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from webextractor.verification.screenshots import ScreenshotComparator


class ComponentDiffReport(list):
    """
    List of per-component region divergence records with threshold-gated status.
    Inherits from list so it behaves directly as a list while exposing convenience properties.
    """

    def __init__(
        self,
        items: list[dict[str, Any]] | None = None,
        threshold: float = 5.0,
        breakpoint: int | str | None = None,
    ):
        super().__init__(items or [])
        self.threshold = threshold
        self.breakpoint = breakpoint

    @property
    def flagged(self) -> list[dict[str, Any]]:
        """Returns all component regions where divergence exceeds the configured threshold."""
        return [item for item in self if item.get("flagged")]

    @property
    def passed(self) -> list[dict[str, Any]]:
        """Returns all component regions within the acceptable threshold."""
        return [item for item in self if not item.get("flagged")]

    @property
    def has_divergence(self) -> bool:
        """True if any component region has been flagged above threshold."""
        return any(item.get("flagged") for item in self)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the diff report into a machine-readable summary dict."""
        return {
            "status": "FAIL" if self.has_divergence else "PASS",
            "threshold": self.threshold,
            "breakpoint": self.breakpoint,
            "total_regions": len(self),
            "flagged_count": len(self.flagged),
            "regions": list(self),
        }


class ComponentDiffReportGenerator:
    """
    Per-component visual diff report generator comparing current React-generated output
    against Phase 0 flat export per Phase 1 exit criteria.
    Extracts per-component bounding regions and performs threshold-gated pixel comparison.
    """

    @staticmethod
    def _unpack_pair(
        item: Path | str | dict[str, Any] | tuple[Any, Any] | list[Any] | None,
    ) -> tuple[Path | str | None, dict[str, Any] | None]:
        """Normalizes screenshot or DOM+screenshot pair input."""
        if item is None:
            return None, None
        if isinstance(item, (str, Path)):
            return item, None
        if isinstance(item, (tuple, list)):
            shot: Path | str | None = None
            dom: dict[str, Any] | None = None
            for elem in item:
                if isinstance(elem, (str, Path)):
                    shot = elem
                elif isinstance(elem, dict):
                    dom = elem
            return shot, dom
        if isinstance(item, dict):
            shot = item.get("screenshot") or item.get("screenshot_path") or item.get("image") or item.get("path")
            dom = item.get("dom") or item.get("rendered_dom") or item.get("dom_tree") or item.get("dom_snapshot")
            if not shot and ("tag" in item or "children" in item):
                dom = item
            return shot, dom
        return None, None

    @classmethod
    def extract_regions_from_dom(
        cls,
        dom_tree: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Extracts component bounding regions from a captured DOM tree.
        Uses DomToJsxEmitter section decomposition and semantic container heuristics.
        """
        regions: list[dict[str, Any]] = []

        # 1. Structural section decomposition
        try:
            from webextractor.generator.dom_emitter import DomToJsxEmitter
            _, sections = DomToJsxEmitter.decompose_content_sections(dom_tree)
            for sec in sections:
                node = sec.get("node", {})
                rect = node.get("rect") if isinstance(node, dict) else None
                if rect and rect.get("width", 0) > 0 and rect.get("height", 0) > 0:
                    regions.append({
                        "name": sec.get("name", "Component"),
                        "rect": {
                            "x": int(rect.get("x", 0)),
                            "y": int(rect.get("y", 0)),
                            "width": int(rect.get("width", 0)),
                            "height": int(rect.get("height", 0)),
                        },
                        "tag": sec.get("tag"),
                    })
        except Exception:
            pass

        if regions:
            return regions

        # 2. Recursive search for named or semantic component containers with positive rect
        def search_nodes(node: dict[str, Any], depth: int = 0) -> None:
            if not isinstance(node, dict) or depth > 12:
                return
            attrs = node.get("attributes", {}) if isinstance(node.get("attributes"), dict) else {}
            name = (
                attrs.get("data-component-name")
                or attrs.get("data-framer-name")
                or attrs.get("data-component")
                or node.get("id")
            )
            tag = (node.get("tag") or "").lower()
            rect = node.get("rect")

            is_semantic = tag in ("section", "header", "footer", "nav", "main", "article")
            if (name or is_semantic) and isinstance(rect, dict) and rect.get("width", 0) > 0 and rect.get("height", 0) > 0:
                comp_name = str(name) if name else (tag.capitalize() if tag else "Component")
                regions.append({
                    "name": comp_name,
                    "rect": {
                        "x": int(rect.get("x", 0)),
                        "y": int(rect.get("y", 0)),
                        "width": int(rect.get("width", 0)),
                        "height": int(rect.get("height", 0)),
                    },
                    "tag": tag,
                })
                return

            for child in node.get("children", []):
                if isinstance(child, dict):
                    search_nodes(child, depth + 1)

        search_nodes(dom_tree)
        return regions

    @classmethod
    def generate(
        cls,
        flat_export: Path | str | dict[str, Any] | tuple[Any, Any] | list[Any],
        react_output: Path | str | dict[str, Any] | tuple[Any, Any] | list[Any],
        *,
        components: list[dict[str, Any]] | None = None,
        threshold: float = 5.0,
        color_tolerance: int = 15,
        breakpoint: int | str | None = None,
    ) -> ComponentDiffReport:
        """
        Generates a per-component region visual diff report comparing Phase 0 flat export
        against current React-generated output.
        Returns a ComponentDiffReport list of per-component regions with individual divergence scores
        gated against threshold.
        """
        orig_shot, orig_dom = cls._unpack_pair(flat_export)
        gen_shot, gen_dom = cls._unpack_pair(react_output)

        target_regions: list[dict[str, Any]] = []

        if components:
            for c in components:
                name = c.get("name") or c.get("component") or c.get("id") or "Component"
                rect = c.get("rect") or c.get("bounds") or c.get("bbox")
                if rect and isinstance(rect, dict):
                    target_regions.append({"name": str(name), "rect": rect})
        elif orig_dom:
            target_regions = cls.extract_regions_from_dom(orig_dom)
        elif gen_dom:
            target_regions = cls.extract_regions_from_dom(gen_dom)

        # Fallback: if no component regions found, sample full page from image header
        if not target_regions and orig_shot:
            hdr = ScreenshotComparator.read_png_header(orig_shot)
            if hdr:
                target_regions.append({
                    "name": "FullPage",
                    "rect": {"x": 0, "y": 0, "width": hdr["width"], "height": hdr["height"]},
                })

        # Pre-decode PNGs once for efficiency across all component regions
        orig_decoded = ScreenshotComparator.decode_png_pixels(orig_shot) if orig_shot else None
        gen_decoded = ScreenshotComparator.decode_png_pixels(gen_shot) if gen_shot else None

        records: list[dict[str, Any]] = []

        for reg in target_regions:
            name = reg.get("name", "Component")
            rect = reg.get("rect", {})
            diff_res = ScreenshotComparator.compare_region(
                orig_decoded if orig_decoded else (orig_shot or ""),
                gen_decoded if gen_decoded else (gen_shot or ""),
                rect=rect,
                color_tolerance=color_tolerance,
                threshold=threshold,
            )
            item = {
                "component": name,
                "rect": rect,
                "divergence_score": diff_res["divergence_score"],
                "similarity_score": diff_res["similarity_score"],
                "flagged": diff_res["flagged"],
                "status": diff_res["status"],
                "threshold": threshold,
                "mse": diff_res.get("mse", 0.0),
                "samples_compared": diff_res.get("samples_compared", 0),
                "diff_pixels_count": diff_res.get("diff_pixels_count", 0),
            }
            if breakpoint is not None:
                item["breakpoint"] = breakpoint
            records.append(item)

        return ComponentDiffReport(records, threshold=threshold, breakpoint=breakpoint)


def generate_component_diff_report(
    flat_export: Path | str | dict[str, Any] | tuple[Any, Any] | list[Any],
    react_output: Path | str | dict[str, Any] | tuple[Any, Any] | list[Any],
    *,
    components: list[dict[str, Any]] | None = None,
    threshold: float = 5.0,
    color_tolerance: int = 15,
    breakpoint: int | str | None = None,
) -> ComponentDiffReport:
    """Convenience function generating per-component region diff reports."""
    return ComponentDiffReportGenerator.generate(
        flat_export=flat_export,
        react_output=react_output,
        components=components,
        threshold=threshold,
        color_tolerance=color_tolerance,
        breakpoint=breakpoint,
    )


class VisualDiffScorer:
    """
    Multi-Signal Fidelity and Visual Difference Analysis Engine.
    Combines:
    1. Visual Screenshot Diff (perceptual pixel diff & dimension accuracy)
    2. Asset Integrity Audit (physical existence, valid byte sizes)
    3. Structural Layout & Component Tree Fidelity
    4. Design System & Typography Coverage
    5. Responsive Viewport Rule Preservation
    6. Behavioral Interaction & Animation Mapping
    7. Per-Component Region Visual Diffing (Phase 1 Exit Criteria)
    """

    @classmethod
    def generate_component_diff_report(
        cls,
        flat_export: Path | str | dict[str, Any] | tuple[Any, Any] | list[Any],
        react_output: Path | str | dict[str, Any] | tuple[Any, Any] | list[Any],
        *,
        components: list[dict[str, Any]] | None = None,
        threshold: float = 5.0,
        color_tolerance: int = 15,
        breakpoint: int | str | None = None,
    ) -> ComponentDiffReport:
        """Generates per-component region visual diff report."""
        return ComponentDiffReportGenerator.generate(
            flat_export=flat_export,
            react_output=react_output,
            components=components,
            threshold=threshold,
            color_tolerance=color_tolerance,
            breakpoint=breakpoint,
        )

    @staticmethod
    def calculate_score(
        components_count: int,
        downloaded_assets: int,
        total_assets: int,
        tokens_count: int,
        screenshot_sim: float | None = None,
    ) -> float:
        """
        Calculates an authentic multi-signal fidelity score without artificial floors or ceilings.
        Returns a transparent, metric-grounded percentage [0.0 - 100.0].
        """
        asset_ratio = (downloaded_assets / total_assets) if total_assets > 0 else 1.0
        # Component saturation based on semantic structure (expecting >= 3 components for complete pages)
        component_ratio = min(1.0, components_count / 3.0) if components_count > 0 else 0.0
        # Token saturation (expecting >= 4 design tokens for real design systems)
        token_ratio = min(1.0, tokens_count / 4.0) if tokens_count > 0 else 0.0

        if screenshot_sim is not None:
            # When ground-truth screenshot diff is available: 45% visual + 25% assets + 20% structure + 10% tokens
            score = (
                (screenshot_sim * 0.45)
                + (asset_ratio * 100.0 * 0.25)
                + (component_ratio * 100.0 * 0.20)
                + (token_ratio * 100.0 * 0.10)
            )
        else:
            # When screenshot is not yet rendered: 45% assets + 35% structure + 20% tokens
            score = (
                (asset_ratio * 100.0 * 0.45)
                + (component_ratio * 100.0 * 0.35)
                + (token_ratio * 100.0 * 0.20)
            )

        return round(min(100.0, max(0.0, score)), 1)

    @classmethod
    def evaluate_fidelity(
        cls,
        output_dir: Path | str,
        site_ir: dict[str, Any] | Any,
        original_capture: dict[str, Any] | None = None,
        generated_capture: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Conducts a deep, multi-category audit of the generated project against source evidence.
        Produces categorical PASS/WARN/FAIL status and machine-readable difference vectors.
        """
        out_path = Path(output_dir)
        ir = site_ir.to_dict() if hasattr(site_ir, "to_dict") else dict(site_ir)

        categories: dict[str, dict[str, Any]] = {}

        # -------------------------------------------------------------
        # 1. ASSET INTEGRITY AUDIT
        # -------------------------------------------------------------
        public_dir = out_path / "public"
        asset_bindings = ir.get("asset_bindings", [])
        total_assets = len(asset_bindings)
        physically_present = 0
        missing_assets = []

        for b in asset_bindings:
            lp = b.get("local_path")
            if lp:
                clean_lp = lp.lstrip("/")
                full_path = out_path / clean_lp if clean_lp.startswith("public/") else public_dir / clean_lp.replace("public/", "")
                if full_path.exists() and full_path.stat().st_size > 0:
                    physically_present += 1
                else:
                    missing_assets.append(b.get("source_url") or lp)
            else:
                missing_assets.append(b.get("source_url") or "unresolved")

        asset_score = round((physically_present / total_assets * 100.0), 1) if total_assets > 0 else 100.0
        asset_status = "PASS" if asset_score >= 90.0 else ("WARN" if asset_score >= 65.0 else "FAIL")
        categories["assets"] = {
            "status": asset_status,
            "score": asset_score,
            "physically_present": physically_present,
            "total_referenced": total_assets,
            "missing_count": len(missing_assets),
            "missing_sample": missing_assets[:5],
            "details": f"{physically_present}/{total_assets} referenced assets physically present in public/",
        }

        # -------------------------------------------------------------
        # 2. LAYOUT & COMPONENT HIERARCHY
        # -------------------------------------------------------------
        pages = ir.get("pages", [])
        components_found = 0
        components_dir = out_path / "components"

        expected_comps = []
        if pages:
            for c in pages[0].get("components", []):
                c_name = c.get("name") if isinstance(c, dict) else str(c)
                if c_name:
                    expected_comps.append(c_name)

        written_comps = []
        if components_dir.exists():
            written_comps = [f.stem for f in components_dir.glob("*.tsx")]

        matched_comps = [c for c in expected_comps if c in written_comps]
        layout_score = round((len(matched_comps) / len(expected_comps) * 100.0), 1) if expected_comps else 100.0
        layout_status = "PASS" if layout_score >= 85.0 else ("WARN" if layout_score >= 60.0 else "FAIL")
        categories["layout"] = {
            "status": layout_status,
            "score": layout_score,
            "expected_components": len(expected_comps),
            "generated_components": len(written_comps),
            "matched_components": len(matched_comps),
            "details": f"{len(matched_comps)}/{len(expected_comps)} page components generated",
        }

        # -------------------------------------------------------------
        # 3. TYPOGRAPHY & DESIGN TOKENS
        # -------------------------------------------------------------
        tokens_css = out_path / "styles" / "tokens.css"
        typography_ir = ir.get("typography", {})
        design_system = ir.get("design_system", {})
        colors = design_system.get("colors", {})

        token_checks = []
        if tokens_css.exists():
            css_text = tokens_css.read_text(encoding="utf-8")
            if "--font-display" in css_text:
                token_checks.append(True)
            if "--font-body" in css_text:
                token_checks.append(True)
            if "--color-" in css_text:
                token_checks.append(True)
            if "--container-max-width" in css_text:
                token_checks.append(True)

        type_score = round((sum(1 for c in token_checks if c) / 4.0 * 100.0), 1) if tokens_css.exists() else 0.0
        type_status = "PASS" if type_score >= 75.0 else ("WARN" if type_score >= 50.0 else "FAIL")
        categories["typography"] = {
            "status": type_status,
            "score": type_score,
            "has_tokens_file": tokens_css.exists(),
            "extracted_colors_count": len(colors),
            "extracted_fonts_count": len(typography_ir.get("font_families", [])),
            "details": f"Design tokens: {len(colors)} colors, {len(typography_ir.get('font_families', []))} font families",
        }

        # -------------------------------------------------------------
        # 4. RESPONSIVE MULTI-VIEWPORT COVERAGE
        # -------------------------------------------------------------
        viewports_ir = ir.get("metadata", {}).get("viewport_count", 0)
        responsive_rules = ir.get("responsive_rules", [])
        globals_css = out_path / "styles" / "globals.css"
        has_media_queries = False

        if globals_css.exists():
            g_text = globals_css.read_text(encoding="utf-8")
            has_media_queries = "@media" in g_text

        resp_score = 100.0 if (has_media_queries or len(responsive_rules) > 0) else 70.0
        resp_status = "PASS" if resp_score >= 80.0 else "WARN"
        categories["responsive"] = {
            "status": resp_status,
            "score": resp_score,
            "viewports_captured": viewports_ir,
            "responsive_rules_count": len(responsive_rules),
            "has_media_queries_in_css": has_media_queries,
            "details": f"{len(responsive_rules)} responsive differential rules applied",
        }

        # -------------------------------------------------------------
        # 5. ANIMATIONS & INTERACTIONS
        # -------------------------------------------------------------
        animations_ir = ir.get("animations", {})
        interactions_ir = ir.get("interactions", [])
        has_motion = (out_path / "components" / "MotionRuntime.tsx").exists()
        has_interaction_rt = (out_path / "components" / "InteractionRuntime.tsx").exists()

        # Verify if extracted timing function curves survive into generated output
        timing_fn = animations_ir.get("timing_function") or animations_ir.get("default_easing")
        anim_details = f"{len(animations_ir.get('appear_animations', {}))} motion triggers bound"
        curve_preserved = True

        if timing_fn and timing_fn.lower() not in ("ease", "linear"):
            found_curve = False
            for ext in ("*.css", "*.tsx", "*.html", "*.js"):
                for f in out_path.rglob(ext):
                    try:
                        t = f.read_text("utf-8")
                        if timing_fn in t:
                            found_curve = True
                            break
                    except Exception:
                        pass
                if found_curve:
                    break
            if not found_curve:
                curve_preserved = False
                anim_details += f" (WARNING: curve {timing_fn} missing in output)"
            else:
                anim_details += f" (curve: {timing_fn})"

        has_anim_or_static = has_motion or (out_path / "css" / "styles.css").exists()
        anim_score = 95.0 if (has_anim_or_static and curve_preserved) else (80.0 if has_anim_or_static else 65.0)
        categories["animations"] = {
            "status": "PASS" if anim_score >= 80.0 else "WARN",
            "score": anim_score,
            "motion_runtime_present": has_motion,
            "timing_function_preserved": curve_preserved,
            "timing_function": timing_fn,
            "appear_animations_count": len(animations_ir.get("appear_animations", {})),
            "details": anim_details,
        }

        inter_score = 95.0 if (has_interaction_rt or not interactions_ir) else 75.0
        categories["interactions"] = {
            "status": "PASS" if inter_score >= 80.0 else "WARN",
            "score": inter_score,
            "interaction_runtime_present": has_interaction_rt,
            "reconstructed_interactions": len(interactions_ir),
            "details": f"{len(interactions_ir)} behavioral interactions registered",
        }

        # -------------------------------------------------------------
        # 6. VISUAL SCREENSHOT COMPARISON (IF AVAILABLE)
        # -------------------------------------------------------------
        visual_comps = []
        screenshot_sim = None
        gen_blocked = False
        gen_blocked_reason = ""

        if generated_capture and generated_capture.get("status") == "BLOCKED":
            gen_blocked = True
            gen_blocked_reason = generated_capture.get("error", "Visual comparison execution was blocked")

        if original_capture and generated_capture and not gen_blocked:
            orig_screens = original_capture.get("screenshots", {})
            gen_screens = generated_capture.get("screenshots", {})
            for vp, orig_file in orig_screens.items():
                gen_file = gen_screens.get(vp)
                if not gen_file:
                    vp_clean = vp.replace("vp_", "")
                    for gk, gv in gen_screens.items():
                        if gk.replace("vp_", "") == vp_clean:
                            gen_file = gv
                            break
                if gen_file and Path(orig_file).exists() and Path(gen_file).exists():
                    comp_res = ScreenshotComparator.compare_screenshots(orig_file, gen_file)
                    comp_res["viewport"] = vp

                    visual_comps.append(comp_res)

            if visual_comps:
                screenshot_sim = sum(c["similarity_score"] for c in visual_comps) / len(visual_comps)

        if visual_comps and screenshot_sim is not None:
            v_status = "PASS" if screenshot_sim >= 85.0 else ("WARN" if screenshot_sim >= 65.0 else "FAIL")
            categories["visual"] = {
                "status": v_status,
                "score": round(screenshot_sim, 1),
                "comparisons_count": len(visual_comps),
                "details": f"{len(visual_comps)} viewports visually compared (avg similarity: {round(screenshot_sim, 1)}%)",
            }
        elif gen_blocked:
            categories["visual"] = {
                "status": "BLOCKED",
                "score": None,
                "comparisons_count": 0,
                "details": f"Visual comparison blocked: {gen_blocked_reason}",
            }
        else:
            categories["visual"] = {
                "status": "NOT_RUN",
                "score": None,
                "comparisons_count": 0,
                "details": "Visual screenshot comparison not executed or screenshots missing",
            }

        # -------------------------------------------------------------
        # OVERALL FIDELITY SCORE & HONEST STATUS
        # -------------------------------------------------------------
        overall = cls.calculate_score(
            components_count=len(matched_comps),
            downloaded_assets=physically_present,
            total_assets=total_assets,
            tokens_count=len(colors),
            screenshot_sim=screenshot_sim,
        )

        v_status = categories["visual"]["status"]
        if v_status == "FAIL":
            overall_status = "FAIL"
        elif v_status == "BLOCKED":
            overall_status = "BLOCKED"
        elif v_status == "NOT_RUN":
            # Stage 7 Requirement: Never allow overall status to become PASS without actual visual comparison evidence!
            overall_status = "NOT_RUN"
        elif v_status == "WARN":
            overall_status = "WARN"
        elif v_status == "PASS":
            overall_status = "PASS" if overall >= 85.0 else ("WARN" if overall >= 65.0 else "FAIL")
        else:
            overall_status = "NOT_RUN"

        return {
            "status": overall_status,
            "overall_score": overall,
            "categories": categories,
            "visual_comparisons": visual_comps,
            "timestamp": str(Path(out_path).stat().st_mtime if out_path.exists() else 0),
        }
