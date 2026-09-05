import json
import tempfile
import unittest
from pathlib import Path

from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.analysis.layout_engine import (
    LayoutFidelityEngine,
    NormalizedLayout,
    ObservedLayout,
)
from webextractor.generator.project import ReactProjectGenerator
from webextractor.model.site_ir import SiteIR


class TestLayoutFidelitySystem(unittest.TestCase):

    def setUp(self):
        self.engine = LayoutFidelityEngine()

        self.mock_desktop_dom = {
            "tag": "body",
            "children": [
                {
                    "tag": "header",
                    "id": "header-nav",
                    "styles": {
                        "display": "flex",
                        "flexDirection": "row",
                        "justifyContent": "space-between",
                        "alignItems": "center",
                        "gap": "32px",
                        "maxWidth": "1280px",
                        "margin": "0 auto",
                        "padding": "24px 48px",
                    },
                    "children": [
                        {"tag": "div", "id": "logo", "children": []},
                        {"tag": "nav", "id": "nav-menu", "children": []},
                    ],
                },
                {
                    "tag": "section",
                    "id": "hero",
                    "styles": {
                        "display": "flex",
                        "flexDirection": "column",
                        "justifyContent": "center",
                        "alignItems": "flex-start",
                        "position": "relative",
                        "gap": "28px",
                        "maxWidth": "1280px",
                        "padding": "100px 48px",
                        "margin": "0 auto",
                        "overflow": "hidden",
                    },
                    "children": [
                        {"tag": "span", "id": "eyebrow", "children": []},
                        {"tag": "h1", "id": "hero-heading", "children": []},
                        {"tag": "p", "id": "hero-desc", "children": []},
                    ],
                },
                {
                    "tag": "section",
                    "id": "projects",
                    "styles": {
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fit, minmax(320px, 1fr))",
                        "gridTemplateRows": "auto",
                        "gap": "32px",
                        "maxWidth": "1280px",
                        "padding": "80px 48px",
                        "margin": "0 auto",
                    },
                    "children": [
                        {"tag": "div", "classes": ["project-card"], "children": []},
                        {"tag": "div", "classes": ["project-card"], "children": []},
                    ],
                },
                {
                    "tag": "div",
                    "classes": ["project-card"],
                    "styles": {
                        "display": "flex",
                        "flexDirection": "column",
                        "padding": "24px",
                        "borderRadius": "12px",
                        "gap": "16px",
                        "borderWidth": "1px",
                    },
                    "children": [],
                },
            ],
        }

        self.mock_tablet_dom = {
            "tag": "body",
            "children": [
                {
                    "tag": "section",
                    "id": "hero",
                    "styles": {
                        "display": "flex",
                        "flexDirection": "column",
                        "gap": "20px",
                        "padding": "60px 32px",
                    },
                    "children": [
                        {"tag": "span", "id": "eyebrow", "children": []},
                        {"tag": "h1", "id": "hero-heading", "children": []},
                        {"tag": "p", "id": "hero-desc", "children": []},
                    ],
                }
            ],
        }

        self.mock_mobile_dom = {
            "tag": "body",
            "children": [
                {
                    "tag": "header",
                    "id": "header-nav",
                    "styles": {
                        "display": "flex",
                        "flexDirection": "column",
                        "gap": "16px",
                        "padding": "16px 20px",
                    },
                    "children": [
                        {"tag": "div", "id": "logo", "children": []},
                        {"tag": "nav", "id": "nav-menu", "children": []},
                    ],
                },
                {
                    "tag": "section",
                    "id": "hero",
                    "styles": {
                        "display": "flex",
                        "flexDirection": "column",
                        "gap": "16px",
                        "padding": "48px 20px",
                    },
                    "children": [
                        {"tag": "span", "id": "eyebrow", "children": []},
                        {"tag": "h1", "id": "hero-heading", "children": []},
                        {"tag": "p", "id": "hero-desc", "children": []},
                    ],
                },
                {
                    "tag": "section",
                    "id": "projects",
                    "styles": {
                        "display": "grid",
                        "gridTemplateColumns": "1fr",
                        "gap": "20px",
                        "padding": "40px 20px",
                    },
                    "children": [
                        {"tag": "div", "classes": ["project-card"], "children": []},
                    ],
                },
            ],
        }

    # 1. Flex layout extraction
    def test_flex_layout_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
        )
        norm_hero = result["normalized"]["Hero"]["desktop"]
        self.assertEqual(norm_hero["layout_type"], "flex")
        self.assertEqual(norm_hero["direction"], "column")
        self.assertEqual(norm_hero["justify"], "center")
        self.assertEqual(norm_hero["align"], "flex-start")
        self.assertEqual(norm_hero["gap"], "28px")

    # 2. Grid layout extraction
    def test_grid_layout_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
        )
        norm_projects = result["normalized"]["Projects"]["desktop"]
        self.assertEqual(norm_projects["layout_type"], "grid")
        self.assertIn("grid", norm_projects)
        self.assertEqual(norm_projects["grid"]["columns"], "repeat(auto-fit, minmax(320px, 1fr))")
        self.assertEqual(norm_projects["grid"]["gap"], "32px")

    # 3. Container / max-width extraction
    def test_container_max_width_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
        )
        container = result["normalized"]["Hero"]["desktop"]["container"]
        self.assertEqual(container["max_width"], "1280px")
        self.assertTrue(container["is_centered"])
        self.assertEqual(container["padding"], "100px 48px")

    # 4. Padding and margin extraction
    def test_padding_margin_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
        )
        obs_header = result["observed"]["desktop"]["HeaderNavigation"]
        self.assertEqual(obs_header["padding"], "24px 48px")
        self.assertEqual(obs_header["margin"], "0 auto")

    # 5. Gap extraction
    def test_gap_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
        )
        card_norm = result["normalized"]["ProjectCard"]["desktop"]
        self.assertEqual(card_norm["gap"], "16px")

    # 6. Alignment extraction
    def test_alignment_extraction(self):
        align_center = self.engine._normalize_align("center")
        align_start = self.engine._normalize_align("flex-start")
        align_stretch = self.engine._normalize_align("stretch")
        self.assertEqual(align_center, "center")
        self.assertEqual(align_start, "flex-start")
        self.assertEqual(align_stretch, "stretch")

        just_between = self.engine._normalize_justify("space-between")
        just_center = self.engine._normalize_justify("center")
        self.assertEqual(just_between, "space-between")
        self.assertEqual(just_center, "center")

    # 7. Positioning extraction (avoids brittle screenshot coordinates)
    def test_positioning_extraction(self):
        brittle_node = {
            "tag": "div",
            "id": "hero",
            "styles": {
                "position": "absolute",
                "top": "137.25px",
                "left": "43.71875px",
                "zIndex": "2",
                "display": "flex",
                "flexDirection": "column",
                "maxWidth": "1200px",
                "padding": "60px 40px",
            }
        }
        obs = self.engine.extract_observed_from_node(brittle_node)
        self.assertEqual(obs.position, "absolute")
        self.assertEqual(obs.top, "137.25px")
        self.assertEqual(obs.left, "43.71875px")

        norm = self.engine._normalize_single_layout(obs, "Hero")
        # Structural positioning should recognize layer/overlay without forcing 137.25px into component container
        self.assertEqual(norm.positioning["position"], "absolute")
        self.assertTrue(norm.positioning["is_layer"])
        self.assertEqual(norm.container["max_width"], "1200px")
        self.assertEqual(norm.container["padding"], "60px 40px")

    # 8. Responsive layout differences (multi-breakpoint)
    def test_responsive_layout_differences(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "tablet": {"dom": self.mock_tablet_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
        )
        hero_norm = result["normalized"]["Hero"]
        self.assertIn("tablet", hero_norm["responsive"])
        self.assertIn("mobile", hero_norm["responsive"])
        self.assertEqual(hero_norm["responsive"]["tablet"]["gap"], "20px")
        self.assertEqual(hero_norm["responsive"]["mobile"]["gap"], "16px")

    # 9. Structural-vs-style responsive variation
    def test_structural_vs_style_responsive_variation(self):
        # Style variation: same children, changed direction/gap
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
        )
        self.assertEqual(result["normalized"]["Hero"]["responsive_variation_type"], "style")

        # Structural variation: children composition/order altered
        structural_desktop = {
            "tag": "section",
            "id": "hero",
            "styles": {"display": "flex"},
            "children": [
                {"tag": "img", "id": "hero-img", "children": []},
                {"tag": "div", "id": "hero-content", "children": []},
            ],
        }
        structural_mobile = {
            "tag": "section",
            "id": "hero",
            "styles": {"display": "flex"},
            "children": [
                {"tag": "div", "id": "hero-content", "children": []},
                {"tag": "img", "id": "hero-img", "children": []},
            ],
        }
        struct_res = self.engine.analyze(
            rendered_dom=structural_desktop,
            viewports={
                "desktop": {"dom": structural_desktop},
                "mobile": {"dom": structural_mobile},
            },
        )
        hero_struct = struct_res["normalized"]["Hero"]
        self.assertEqual(hero_struct["responsive_variation_type"], "structural")
        self.assertEqual(hero_struct["child_order"]["desktop"], ["img#hero-img", "div#hero-content"])
        self.assertEqual(hero_struct["child_order"]["mobile"], ["div#hero-content", "img#hero-img"])

    # 10. Normalized layout generation (Layer A + Layer B separation)
    def test_normalized_layout_generation(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
        )
        self.assertIn("observed", result)
        self.assertIn("normalized", result)
        self.assertIn("tokens", result)

        # Layer A preserves raw evidence
        self.assertIn("display", result["observed"]["desktop"]["Hero"])
        self.assertIn("padding", result["observed"]["desktop"]["Hero"])

        # Layer B models reusable structural relationships
        self.assertIn("layout_type", result["normalized"]["Hero"]["desktop"])
        self.assertIn("container", result["normalized"]["Hero"]["desktop"])

    # 11. Deterministic output
    def test_deterministic_output(self):
        run_1 = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
        )
        run_2 = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
        )
        self.assertEqual(json.dumps(run_1, sort_keys=True), json.dumps(run_2, sort_keys=True))

    # 12. Unsupported / missing layout behavior
    def test_unsupported_missing_layout_behavior(self):
        weird_node = {
            "tag": "div",
            "id": "hero",
            "styles": {
                "display": "table-cell",
                "alignItems": "weird-unknown-value",
            },
            "rect": None,
        }
        obs = self.engine.extract_observed_from_node(weird_node)
        norm = self.engine._normalize_single_layout(obs, "Hero")
        self.assertTrue(len(norm.unsupported) > 0)
        self.assertIn("unsupported display: table-cell", norm.unsupported[0])
        # Safe fallback
        self.assertEqual(norm.align, "stretch")

    # 13. React generator layout consumption
    def test_react_generator_layout_consumption(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            generator = ReactProjectGenerator(
                site_ir={
                    "layout": result,
                    "design_system": {},
                    "pages": [{"name": "Home", "components": ["HeaderNavigation", "Hero", "Projects"]}],
                },
                output_dir=temp_dir,
            )
            generator._create_structure()
            generator._write_tokens()
            generator._write_global_styles()

            tokens_css = (Path(temp_dir) / "styles/tokens.css").read_text(encoding="utf-8")
            self.assertIn("--container-max-width: 1280px;", tokens_css)
            self.assertIn("--layout-gap-", tokens_css)

            globals_css = (Path(temp_dir) / "app/globals.css").read_text(encoding="utf-8")
            self.assertIn(".hero {\n", globals_css)
            self.assertIn("display: flex;", globals_css)
            self.assertIn("max-width: 1280px;", globals_css)
            self.assertIn("@media (max-width: 768px)", globals_css)

    # 14. Non-regression of Phase 5A
    def test_regression_phase_5a(self):
        mock_capture = {
            "url": "https://origins.example.com",
            "html": "<html><head><title>Origins</title></head><body><header>Nav</header><section id='hero'><h1>Mohamed Shaheem</h1></section></body></html>",
            "dom": self.mock_desktop_dom,
            "viewports": {"desktop": {"dom": self.mock_desktop_dom}},
        }
        analyzer = SiteAnalyzer()
        site_model = analyzer.analyze(mock_capture)
        self.assertTrue(hasattr(site_model, "layout"))
        self.assertIn("normalized", site_model.layout)
        self.assertIn("Hero", site_model.layout["normalized"])

    # 15. Non-regression of Phase 5B.1 (Asset Bindings)
    def test_regression_phase_5b1(self):
        mock_capture = {
            "url": "https://origins.example.com",
            "html": "<html><head><title>Origins</title></head><body><header>Nav</header><section id='hero'><h1>Mohamed Shaheem</h1></section></body></html>",
            "dom": self.mock_desktop_dom,
            "asset_manifest": [
                {
                    "source": "https://origins.example.com/logo.svg",
                    "local": "/images/logo.svg",
                    "category": "images",
                }
            ],
            "viewports": {"desktop": {"dom": self.mock_desktop_dom}},
        }
        analyzer = SiteAnalyzer()
        site_model = analyzer.analyze(mock_capture)
        self.assertTrue(hasattr(site_model, "asset_bindings"))
        self.assertTrue(hasattr(site_model, "layout"))

    # 16. Non-regression of Phase 5B.2 (Typography)
    def test_regression_phase_5b2(self):
        mock_capture = {
            "url": "https://origins.example.com",
            "html": "<html><head><title>Origins</title></head><body><header>Nav</header><section id='hero'><h1>Mohamed Shaheem</h1></section></body></html>",
            "dom": self.mock_desktop_dom,
            "viewports": {"desktop": {"dom": self.mock_desktop_dom}},
        }
        analyzer = SiteAnalyzer()
        site_model = analyzer.analyze(mock_capture)
        self.assertTrue(hasattr(site_model, "typography"))
        self.assertIn("font_families", site_model.typography)
        self.assertIn("roles", site_model.typography)


if __name__ == "__main__":
    unittest.main()
