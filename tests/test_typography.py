import json
import tempfile
import unittest
from pathlib import Path

from webextractor.analysis.typography_engine import (
    FontFamilyDefinition,
    TypographyEngine,
    TypographyRoleDefinition,
)
from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.generator.project import ReactProjectGenerator
from webextractor.model.site_ir import SiteIR


class TestTypographySystem(unittest.TestCase):

    def setUp(self):
        self.engine = TypographyEngine()

        self.mock_desktop_dom = {
            "tag": "body",
            "children": [
                {
                    "tag": "header",
                    "styles": {
                        "fontFamily": "'Inter', -apple-system, sans-serif",
                    },
                    "children": [
                        {
                            "tag": "nav",
                            "styles": {
                                "fontFamily": "'Inter', sans-serif",
                                "fontSize": "14px",
                                "fontWeight": "500",
                                "lineHeight": "1.4",
                            },
                            "children": [],
                        }
                    ]
                },
                {
                    "tag": "section",
                    "id": "hero",
                    "children": [
                        {
                            "tag": "span",
                            "styles": {
                                "fontSize": "12px",
                                "fontWeight": "600",
                                "letterSpacing": "0.2em",
                                "textTransform": "uppercase",
                                "fontFamily": "'Inter', sans-serif",
                            },
                        },
                        {
                            "tag": "h1",
                            "styles": {
                                "fontFamily": '"Clash Display", sans-serif',
                                "fontSize": "84px",
                                "fontWeight": "800",
                                "lineHeight": "1.04",
                                "letterSpacing": "-0.03em",
                                "textTransform": "none",
                            },
                        },
                        {
                            "tag": "p",
                            "styles": {
                                "fontFamily": "'Inter', sans-serif",
                                "fontSize": "18px",
                                "fontWeight": "400",
                                "lineHeight": "1.6",
                                "fontStyle": "normal",
                            },
                        }
                    ]
                },
                {
                    "tag": "section",
                    "id": "projects",
                    "children": [
                        {
                            "tag": "h2",
                            "styles": {
                                "fontFamily": '"Clash Display", sans-serif',
                                "fontSize": "44px",
                                "fontWeight": "700",
                                "lineHeight": "1.15",
                                "letterSpacing": "-0.01em",
                            },
                        },
                        {
                            "tag": "h3",
                            "styles": {
                                "fontFamily": '"Clash Display", sans-serif',
                                "fontSize": "24px",
                                "fontWeight": "600",
                                "lineHeight": "1.25",
                            },
                        },
                        {
                            "tag": "button",
                            "styles": {
                                "fontFamily": "'Inter', sans-serif",
                                "fontSize": "15px",
                                "fontWeight": "600",
                                "lineHeight": "1.2",
                            },
                        }
                    ]
                }
            ]
        }

        self.mock_mobile_dom = {
            "tag": "body",
            "children": [
                {
                    "tag": "section",
                    "id": "hero",
                    "children": [
                        {
                            "tag": "h1",
                            "styles": {
                                "fontFamily": '"Clash Display", sans-serif',
                                "fontSize": "48px",
                                "fontWeight": "800",
                                "lineHeight": "1.08",
                            },
                        }
                    ]
                },
                {
                    "tag": "section",
                    "id": "projects",
                    "children": [
                        {
                            "tag": "h2",
                            "styles": {
                                "fontFamily": '"Clash Display", sans-serif',
                                "fontSize": "32px",
                                "fontWeight": "700",
                                "lineHeight": "1.2",
                            },
                        }
                    ]
                }
            ]
        }

        self.mock_asset_manifest = [
            {
                "source": "https://origins.example.com/assets/fonts/clash-display.woff2",
                "local": "public/fonts/clash-display.woff2",
                "format": "woff2",
                "size_bytes": 48200,
                "category": "fonts",
            }
        ]

    # 1. Typography Extraction
    def test_typography_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
            asset_manifest=self.mock_asset_manifest,
        )

        self.assertIn("font_families", result)
        self.assertIn("roles", result)
        self.assertIn("responsive", result)

        family_names = [f["name"] for f in result["font_families"]]
        self.assertIn("Clash Display", family_names)
        self.assertIn("Inter", family_names)

    # 2. Font Stack Fallback Parsing
    def test_font_stack_fallback_parsing(self):
        primary, fallbacks = self.engine.parse_font_stack('"Clash Display", "General Sans", sans-serif')
        self.assertEqual(primary, "Clash Display")
        self.assertEqual(fallbacks, ["General Sans", "sans-serif"])

        primary2, fallbacks2 = self.engine.parse_font_stack("monospace")
        self.assertEqual(primary2, "monospace")
        self.assertEqual(fallbacks2, ["sans-serif"])

        primary3, fallbacks3 = self.engine.parse_font_stack("")
        self.assertEqual(primary3, "system-ui")
        self.assertIn("sans-serif", fallbacks3)

    # 3. Weight and Style Extraction
    def test_weight_and_style_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
            asset_manifest=self.mock_asset_manifest,
        )

        clash = next(f for f in result["font_families"] if f["name"] == "Clash Display")
        self.assertIn(800, clash["weights"])
        self.assertIn(700, clash["weights"])
        self.assertIn("normal", clash["styles"])

    # 4. Font Size Scale Extraction
    def test_font_size_scale_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
            asset_manifest=self.mock_asset_manifest,
        )

        roles = result["roles"]
        # H1 was 84px (> 80px) -> display role
        self.assertEqual(roles["display"]["font_size"], "84px")
        # H2 was 44px -> heading role
        self.assertEqual(roles["heading"]["font_size"], "44px")
        # P was 18px -> body role
        self.assertEqual(roles["body"]["font_size"], "18px")

    # 5. Line Height Extraction
    def test_line_height_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
            asset_manifest=self.mock_asset_manifest,
        )

        roles = result["roles"]
        self.assertEqual(roles["display"]["line_height"], "1.04")
        self.assertEqual(roles["heading"]["line_height"], "1.15")
        self.assertEqual(roles["body"]["line_height"], "1.6")

    # 6. Letter Spacing Extraction
    def test_letter_spacing_extraction(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
            asset_manifest=self.mock_asset_manifest,
        )

        roles = result["roles"]
        self.assertEqual(roles["display"]["letter_spacing"], "-0.03em")
        self.assertEqual(roles["label"]["letter_spacing"], "0.2em")

    # 7. Semantic Role Assignment
    def test_semantic_role_assignment(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
            asset_manifest=self.mock_asset_manifest,
        )

        roles = result["roles"]
        expected_roles = [
            "display", "hero", "heading", "subheading",
            "body", "caption", "label", "navigation", "button", "mono"
        ]
        for r in expected_roles:
            self.assertIn(r, roles)
            self.assertIn("font_family", roles[r])
            self.assertIn("font_size", roles[r])
            self.assertIn("font_weight", roles[r])

        self.assertEqual(roles["label"]["text_transform"], "uppercase")

    # 8. Responsive Typography Diffing
    def test_responsive_typography_diffing(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
            asset_manifest=self.mock_asset_manifest,
        )

        mobile_diffs = result.get("responsive", {}).get("mobile", {})
        # Desktop H2 was 44px, Mobile H2 was 32px -> heading should have responsive override
        self.assertIn("heading", mobile_diffs)
        self.assertEqual(mobile_diffs["heading"]["font_size"], "32px")
        self.assertEqual(mobile_diffs["heading"]["line_height"], "1.2")

    # 9. CSS Custom Property Generation
    def test_css_custom_property_generation(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
            asset_manifest=self.mock_asset_manifest,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            generator = ReactProjectGenerator(
                site_ir={"typography": result, "design_system": {}},
                output_dir=temp_dir,
            )
            generator._create_structure()
            generator._write_tokens()

            tokens_path = Path(temp_dir) / "styles/tokens.css"
            self.assertTrue(tokens_path.exists())
            tokens_css = tokens_path.read_text(encoding="utf-8")

            self.assertIn("--font-display:", tokens_css)
            self.assertIn("--font-body:", tokens_css)
            self.assertIn("--font-mono:", tokens_css)
            self.assertIn("--type-heading-size: 44px;", tokens_css)
            self.assertIn("--type-heading-weight: 700;", tokens_css)
            self.assertIn("--type-heading-line-height: 1.15;", tokens_css)
            self.assertIn("--type-label-letter-spacing: 0.2em;", tokens_css)
            self.assertIn("--type-label-transform: uppercase;", tokens_css)

            # Check responsive media query
            self.assertIn("@media (max-width: 768px)", tokens_css)
            self.assertIn("--type-heading-size: 32px;", tokens_css)

    # 10. Local @font-face Generation
    def test_local_font_face_generation(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
            asset_manifest=self.mock_asset_manifest,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            generator = ReactProjectGenerator(
                site_ir={"typography": result, "design_system": {}},
                output_dir=temp_dir,
            )
            generator._create_structure()
            generator._write_tokens()

            tokens_css = (Path(temp_dir) / "styles/tokens.css").read_text(encoding="utf-8")

            self.assertIn("@font-face {", tokens_css)
            self.assertIn("font-family: 'Clash Display';", tokens_css)
            self.assertIn("src: url('/fonts/clash-display.woff2');", tokens_css)
            self.assertIn("font-display: swap;", tokens_css)

    # 11. Unresolved Font Fallback Behavior
    def test_unresolved_font_fallback_behavior(self):
        # DOM with a custom webfont not in asset manifest
        unresolved_dom = {
            "tag": "body",
            "children": [
                {
                    "tag": "h1",
                    "styles": {
                        "fontFamily": '"RemoteRareFont", sans-serif',
                        "fontSize": "60px",
                    },
                }
            ]
        }

        result = self.engine.analyze(
            rendered_dom=unresolved_dom,
            viewports={"desktop": {"dom": unresolved_dom}},
            asset_manifest=[],  # No fonts downloaded
        )

        remote_font = next(f for f in result["font_families"] if f["name"] == "RemoteRareFont")
        self.assertEqual(remote_font["source"], "remote")
        self.assertFalse(remote_font["resolved"])
        self.assertIsNone(remote_font["local_path"])
        self.assertEqual(remote_font["fallbacks"], ["sans-serif"])

        with tempfile.TemporaryDirectory() as temp_dir:
            generator = ReactProjectGenerator(
                site_ir={"typography": result, "design_system": {}},
                output_dir=temp_dir,
            )
            generator._create_structure()
            generator._write_tokens()

            tokens_css = (Path(temp_dir) / "styles/tokens.css").read_text(encoding="utf-8")
            # Should NOT output an invalid @font-face for the unresolved font
            self.assertNotIn("font-family: 'RemoteRareFont';", tokens_css.split(":root")[0])
            # Should still safely reference the family with fallbacks in tokens
            self.assertIn("RemoteRareFont", tokens_css)
            self.assertIn("sans-serif", tokens_css)

    # 12. IR Determinism (Repeated Runs)
    def test_ir_determinism_repeated_runs(self):
        result_a = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
            asset_manifest=self.mock_asset_manifest,
        )

        result_b = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
            asset_manifest=self.mock_asset_manifest,
        )

        json_a = json.dumps(result_a, sort_keys=True)
        json_b = json.dumps(result_b, sort_keys=True)
        self.assertEqual(json_a, json_b, "Typography analysis must be completely deterministic")

    # 13. React Component Token Usage
    def test_react_component_token_usage(self):
        result = self.engine.analyze(
            rendered_dom=self.mock_desktop_dom,
            viewports={"desktop": {"dom": self.mock_desktop_dom}},
            asset_manifest=self.mock_asset_manifest,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            generator = ReactProjectGenerator(
                site_ir={
                    "typography": result,
                    "design_system": {},
                    "pages": [{"name": "Home", "components": ["HeaderNavigation", "Hero", "Projects"]}],
                    "reusable_components": ["ProjectCard"],
                },
                output_dir=temp_dir,
            )
            generator.generate()

            hero_code = (Path(temp_dir) / "components/Hero.tsx").read_text(encoding="utf-8")
            self.assertIn("var(--font-display)", hero_code)
            self.assertIn("var(--type-hero-size", hero_code)
            self.assertIn("var(--font-body)", hero_code)

            projects_code = (Path(temp_dir) / "components/Projects.tsx").read_text(encoding="utf-8")
            self.assertIn("var(--font-display)", projects_code)
            self.assertIn("var(--type-heading-size", projects_code)

            card_code = (Path(temp_dir) / "components/ProjectCard.tsx").read_text(encoding="utf-8")
            self.assertIn("var(--font-display)", card_code)
            self.assertIn("var(--type-subheading-size", card_code)
            self.assertIn("var(--font-body)", card_code)

    # 14. Non-regression of Phase 5A and 5B.1
    def test_non_regression_phase_5a_and_5b1(self):
        mock_capture = {
            "url": "https://origins.example.com",
            "html": "<html><head><title>Origins Portfolio</title></head><body><header>Nav</header><section id='hero'><h1>Mohamed Shaheem</h1></section></body></html>",
            "dom": self.mock_desktop_dom,
            "viewports": {
                "desktop": {"dom": self.mock_desktop_dom},
                "mobile": {"dom": self.mock_mobile_dom},
            },
        }

        analyzer = SiteAnalyzer()
        site_model = analyzer.analyze(mock_capture)
        self.assertTrue(hasattr(site_model, "typography"))
        self.assertIn("font_families", site_model.typography)

        with tempfile.TemporaryDirectory() as temp_dir:
            out = Path(temp_dir)
            site_ir = SiteIR(
                metadata={"title": site_model.title, "url": site_model.url},
                routes=site_model.routes,
                design_system=site_model.design_system,
                pages=site_model.pages,
                reusable_components=site_model.reusable_components,
                component_styles=site_model.component_styles,
                data=site_model.data,
                components=site_model.components,
                assets=self.mock_asset_manifest,
                typography=site_model.typography,
            )

            # Persist analysis
            site_ir.save(out / "analysis")
            self.assertTrue((out / "analysis/typography.json").exists())
            self.assertTrue((out / "analysis/site_ir.json").exists())

            generator = ReactProjectGenerator(site_ir, out / "site")
            generator.generate()

            # Ensure complete App Router tree generated
            self.assertTrue((out / "site/app/layout.tsx").exists())
            self.assertTrue((out / "site/app/page.tsx").exists())
            self.assertTrue((out / "site/app/globals.css").exists())
            self.assertTrue((out / "site/styles/tokens.css").exists())
            self.assertTrue((out / "site/components/Hero.tsx").exists())
            self.assertTrue((out / "site/components/ProjectCard.tsx").exists())


if __name__ == "__main__":
    unittest.main()
