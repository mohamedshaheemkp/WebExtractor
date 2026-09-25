from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from webextractor.verification.screenshots import ScreenshotComparator


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
    """

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

        if original_capture and generated_capture:
            orig_screens = original_capture.get("screenshots", {})
            gen_screens = generated_capture.get("screenshots", {})
            for vp, orig_file in orig_screens.items():
                gen_file = gen_screens.get(vp)
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
        else:
            categories["visual"] = {
                "status": "NOT_RUN",
                "score": None,
                "comparisons_count": 0,
                "details": "Visual screenshot comparison not executed or screenshots missing",
            }

        # -------------------------------------------------------------
        # OVERALL FIDELITY SCORE
        # -------------------------------------------------------------
        overall = cls.calculate_score(
            components_count=len(matched_comps),
            downloaded_assets=physically_present,
            total_assets=total_assets,
            tokens_count=len(colors),
            screenshot_sim=screenshot_sim,
        )

        if categories["visual"]["status"] == "FAIL":
            overall_status = "FAIL"
        elif categories["visual"]["status"] == "WARN":
            overall_status = "WARN"
        else:
            overall_status = "PASS" if overall >= 85.0 else ("WARN" if overall >= 65.0 else "FAIL")

        return {
            "status": overall_status,
            "overall_score": overall,
            "categories": categories,
            "visual_comparisons": visual_comps,
            "timestamp": str(Path(out_path).stat().st_mtime if out_path.exists() else 0),
        }
