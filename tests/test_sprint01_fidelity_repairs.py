import unittest
from pathlib import Path
import tempfile
import shutil

from webextractor.model.asset import Asset, AssetType
from webextractor.assets.organizer import AssetOrganizer
from webextractor.analysis.motion_adapters.standard import StandardCssMotionAdapter
from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.capture.multi_viewport import MultiViewportCapture
from webextractor.generator.static import StaticProjectGenerator
from webextractor.generator.project import ReactProjectGenerator
from webextractor.verification.visual_diff import VisualDiffScorer


class TestSprint01FidelityRepairs(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_asset_organizer_classification_integrity(self):
        """Validates that .mjs, .js, .css, and .html files never enter images/."""
        project_dir = self.temp_dir / "project"
        project_dir.mkdir()
        cache_dir = self.temp_dir / "cache"
        cache_dir.mkdir()

        # Create dummy downloaded files
        f_js = cache_dir / "chunk-123.mjs"
        f_js.write_text("console.log('test');", encoding="utf-8")
        f_css = cache_dir / "bundle.css"
        f_css.write_text("body { color: red; }", encoding="utf-8")
        f_html = cache_dir / "sandbox.html"
        f_html.write_text("<div>test</div>", encoding="utf-8")
        f_img = cache_dir / "hero.png"
        f_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

        assets = [
            Asset(url="https://example.com/chunk-123.mjs", filename="chunk-123.mjs", extension="mjs", downloaded=True, local_path=f_js),
            Asset(url="https://example.com/bundle.css", filename="bundle.css", extension="css", downloaded=True, local_path=f_css),
            Asset(url="https://example.com/sandbox.html", filename="sandbox.html", extension="html", downloaded=True, local_path=f_html),
            Asset(url="https://example.com/hero.png", filename="hero.png", extension="png", downloaded=True, local_path=f_img),
        ]

        AssetOrganizer.organize_assets(assets, project_dir)

        # Invariants:
        self.assertTrue((project_dir / "public" / "scripts" / "chunk-123.mjs").exists())
        self.assertTrue((project_dir / "public" / "styles" / "bundle.css").exists())
        self.assertTrue((project_dir / "public" / "documents" / "sandbox.html").exists())
        self.assertTrue((project_dir / "public" / "images" / "hero.png").exists())

        # Absolutely no scripts or stylesheets in images
        image_files = [f.name for f in (project_dir / "public" / "images").iterdir()]
        self.assertNotIn("chunk-123.mjs", image_files)
        self.assertNotIn("bundle.css", image_files)
        self.assertNotIn("sandbox.html", image_files)
        self.assertIn("hero.png", image_files)

    def test_motion_adapter_easing_preservation(self):
        """Validates that StandardCssMotionAdapter extracts cubic-bezier and steps curves."""
        adapter = StandardCssMotionAdapter()

        # 1. Cubic-bezier transition
        css_cubic = "body { transition: transform 1.2s cubic-bezier(0.44, 0, 0.56, 1) 0.1s; }"
        res = adapter.extract_motion("<html></html>", css_cubic)
        self.assertAlmostEqual(res["default_transition_duration"], 1.2, places=2)
        self.assertEqual(res["default_easing"], "cubic-bezier(0.44, 0, 0.56, 1)")

        # 2. Steps transition
        css_steps = ".sprite { transition: background-position 0.8s steps(4, jump-end); }"
        res2 = adapter.extract_motion("<html></html>", css_steps)
        self.assertAlmostEqual(res2["default_transition_duration"], 0.8, places=2)
        self.assertEqual(res2["default_easing"], "steps(4, jump-end)")

    def test_analyzer_preserves_easing_in_ir(self):
        """Validates that SiteAnalyzer incorporates extracted easing into transition config."""
        analyzer = SiteAnalyzer()
        capture = {
            "url": "https://example.com",
            "html": "<html><body><div id='hero'>Hero</div></body></html>",
            "css": "body { transition: opacity 1.2s cubic-bezier(0.44, 0, 0.56, 1); }",
            "reveal_candidates": [
                {
                    "id": "hero-rev",
                    "initial": {"opacity": 0, "x": 0, "y": 30},
                    "final": {"opacity": 1, "x": 0, "y": 0},
                    "easing": "cubic-bezier(0.44, 0, 0.56, 1)",
                    "duration": "1.2s",
                }
            ]
        }
        site_ir = analyzer.analyze(capture)
        appear = site_ir.animations.get("appear_animations", {})
        self.assertIn("hero-rev", appear)
        transition = appear["hero-rev"]["transition"]
        self.assertEqual(transition["duration"], 1.2)
        self.assertEqual(transition["easing"], "cubic-bezier(0.44, 0, 0.56, 1)")

    def test_responsive_css_emission(self):
        """Validates that responsive rules are emitted into styles.css with clean selectors."""
        out_dir = self.temp_dir / "static_test"
        out_dir.mkdir()

        mock_ir = {
            "metadata": {"title": "Test Site"},
            "routes": ["/"],
            "design_system": {"colors": {"bg": "#000"}, "radii": {}},
            "typography": {"font_families": [{"name": "Inter"}]},
            "layout": {"tokens": {"container_max_width": "1280px"}},
            "pages": [{"route": "/", "title": "Home", "tree": {"tag": "div", "classes": ["container"]}}],
            "responsive_rules": [
                {
                    "selector": ".framer-hero",
                    "media_query": "@media (max-width: 768px)",
                    "breakpoint": "mobile",
                    "diffs": {
                        "width": {"desktop": "1440px", "mobile": "100%"},
                        "fontSize": {"desktop": "48px", "mobile": "24px"},
                    }
                }
            ],
            "animations": {
                "default_transition_duration": 1.2,
                "default_easing": "cubic-bezier(0.44, 0, 0.56, 1)",
            },
            "asset_bindings": [],
        }

        gen = StaticProjectGenerator(mock_ir, out_dir)
        gen.generate()

        css_content = (out_dir / "css" / "styles.css").read_text("utf-8")
        # Verify media query emission
        self.assertIn("@media (max-width: 768px)", css_content)
        self.assertIn(".framer-hero", css_content)
        self.assertIn("width: 100% !important;", css_content)
        self.assertIn("font-size: 24px !important;", css_content)
        # Verify dynamic easing in wx-reveal
        self.assertIn("cubic-bezier(0.44, 0, 0.56, 1)", css_content)

    def test_validation_engine_integrity(self):
        """Validates that VisualDiffScorer accurately tracks NOT_RUN and visual discrepancies."""
        out_dir = self.temp_dir / "audit_test"
        out_dir.mkdir()
        (out_dir / "components").mkdir()
        (out_dir / "public").mkdir()
        (out_dir / "styles").mkdir()
        (out_dir / "styles" / "tokens.css").write_text(":root { --font-display: Inter; --color-bg: #000; }", encoding="utf-8")
        (out_dir / "components" / "Hero.tsx").write_text("export default function Hero() {}", encoding="utf-8")

        mock_ir = {
            "pages": [{"components": ["Hero"]}],
            "design_system": {"colors": {"bg": "#000"}},
            "typography": {"font_families": [{"name": "Inter"}]},
            "asset_bindings": [],
            "responsive_rules": [],
            "animations": {},
            "interactions": [],
        }

        # 1. When screenshots are not passed, category visual must be NOT_RUN
        res_no_ss = VisualDiffScorer.evaluate_fidelity(out_dir, mock_ir)
        self.assertEqual(res_no_ss["categories"]["visual"]["status"], "NOT_RUN")
        self.assertIsNone(res_no_ss["categories"]["visual"]["score"])

        # 2. When screenshots fail visual diff, overall status must reflect failure
        orig_cap = {"screenshots": {"desktop": str(self.temp_dir / "missing_orig.png")}}
        gen_cap = {"screenshots": {"desktop": str(self.temp_dir / "missing_gen.png")}}
        res_with_missing = VisualDiffScorer.evaluate_fidelity(out_dir, mock_ir, original_capture=orig_cap, generated_capture=gen_cap)
        self.assertEqual(res_with_missing["categories"]["visual"]["status"], "NOT_RUN")

    def test_timing_function_cubic_bezier_survival(self):
        """Regression test: source cubic-bezier(...) must survive into generated output, never replaced with ease."""
        css_source = ".hero-card { transition: transform 1.2s cubic-bezier(0.44, 0, 0.56, 1); }"
        adapter = StandardCssMotionAdapter()
        res = adapter.extract_motion("<div></div>", css_source)

        self.assertEqual(res["timing_function"], "cubic-bezier(0.44, 0, 0.56, 1)")
        self.assertEqual(res["default_easing"], "cubic-bezier(0.44, 0, 0.56, 1)")
        self.assertIn(".hero-card", res["element_transitions"])
        self.assertEqual(res["element_transitions"][".hero-card"]["timing_function"], "cubic-bezier(0.44, 0, 0.56, 1)")

        # Verify generation in static CSS
        out_dir = self.temp_dir / "cubic_test"
        out_dir.mkdir()
        mock_ir = {
            "metadata": {"title": "Cubic Test"},
            "routes": ["/"],
            "design_system": {"colors": {}},
            "typography": {"font_families": []},
            "layout": {"tokens": {}},
            "pages": [{"route": "/", "title": "Home", "tree": {"tag": "div"}}],
            "responsive_rules": [],
            "animations": {
                "default_transition_duration": 1.2,
                "timing_function": "cubic-bezier(0.44, 0, 0.56, 1)",
                "default_easing": "cubic-bezier(0.44, 0, 0.56, 1)",
                "element_transitions": {
                    ".hero-card": {
                        "duration": 1.2,
                        "timing_function": "cubic-bezier(0.44, 0, 0.56, 1)",
                    }
                }
            },
            "asset_bindings": [],
        }

        gen = StaticProjectGenerator(mock_ir, out_dir)
        gen.generate()
        css_text = (out_dir / "css" / "styles.css").read_text("utf-8")

        # Invariants:
        self.assertIn("cubic-bezier(0.44, 0, 0.56, 1)", css_text)
        self.assertIn(".hero-card", css_text)
        self.assertIn("transition: all 1.2s cubic-bezier(0.44, 0, 0.56, 1) !important;", css_text)
        # Crucial regression invariant: must NOT be replaced with generic 'ease'
        self.assertNotIn("transition: all 1.2s ease !important;", css_text)

    def test_timing_function_steps_survival(self):
        """Regression test: arbitrary steps(...) timing functions must survive into generated output."""
        css_source = ".sprite { transition: background-position 0.8s steps(4, jump-end); }"
        adapter = StandardCssMotionAdapter()
        res = adapter.extract_motion("<div></div>", css_source)

        self.assertEqual(res["timing_function"], "steps(4, jump-end)")
        self.assertIn(".sprite", res["element_transitions"])
        self.assertEqual(res["element_transitions"][".sprite"]["timing_function"], "steps(4, jump-end)")

        # Verify generation in static CSS
        out_dir = self.temp_dir / "steps_test"
        out_dir.mkdir()
        mock_ir = {
            "metadata": {"title": "Steps Test"},
            "routes": ["/"],
            "design_system": {"colors": {}},
            "typography": {"font_families": []},
            "layout": {"tokens": {}},
            "pages": [{"route": "/", "title": "Home", "tree": {"tag": "div"}}],
            "responsive_rules": [],
            "animations": {
                "default_transition_duration": 0.8,
                "timing_function": "steps(4, jump-end)",
                "default_easing": "steps(4, jump-end)",
                "element_transitions": {
                    ".sprite": {
                        "duration": 0.8,
                        "timing_function": "steps(4, jump-end)",
                    }
                }
            },
            "asset_bindings": [],
        }

        gen = StaticProjectGenerator(mock_ir, out_dir)
        gen.generate()
        css_text = (out_dir / "css" / "styles.css").read_text("utf-8")

        self.assertIn("steps(4, jump-end)", css_text)
        self.assertIn(".sprite", css_text)
        self.assertIn("transition: all 0.8s steps(4, jump-end) !important;", css_text)

    def test_dom_computed_style_transition_propagation(self):
        """Validates that computed styles with cubic-bezier from DOM tree are captured into SiteIR."""
        analyzer = SiteAnalyzer()
        capture = {
            "url": "https://example.com",
            "html": "<html><body><div id='form-input' class='framer-1v98nax'>Input</div></body></html>",
            "dom": {
                "tag": "div",
                "id": "form-input",
                "classes": ["framer-1v98nax"],
                "styles": {
                    "transitionTimingFunction": "cubic-bezier(0.44, 0, 0.56, 1)",
                    "transitionDuration": "0.3s",
                    "transition": "all 0.3s cubic-bezier(0.44, 0, 0.56, 1) 0s",
                },
                "children": [],
            }
        }
        site_ir = analyzer.analyze(capture)
        anims = site_ir.animations
        self.assertIn("element_transitions", anims)
        self.assertIn("#form-input", anims["element_transitions"])
        el_trans = anims["element_transitions"]["#form-input"]
        self.assertEqual(el_trans["timing_function"], "cubic-bezier(0.44, 0, 0.56, 1)")
        self.assertEqual(el_trans["duration"], 0.3)
        self.assertEqual(anims.get("timing_function"), "cubic-bezier(0.44, 0, 0.56, 1)")

    def test_custom_viewports_responsive_rules_emission(self):
        """Validates that _extract_responsive_rules handles vp_1440 and vp_768 custom viewport keys."""
        mvc = MultiViewportCapture(output_dir="")
        viewports_data = {
            "vp_1440": {
                "viewport": {"width": 1440, "height": 900},
                "dom": {
                    "tag": "div",
                    "id": "hero",
                    "classes": ["hero-section"],
                    "styles": {"width": "1440px", "fontSize": "48px"},
                    "children": [],
                }
            },
            "vp_768": {
                "viewport": {"width": 768, "height": 800},
                "dom": {
                    "tag": "div",
                    "id": "hero",
                    "classes": ["hero-section"],
                    "styles": {"width": "768px", "fontSize": "32px"},
                    "children": [],
                }
            },
            "vp_375": {
                "viewport": {"width": 375, "height": 812},
                "dom": {
                    "tag": "div",
                    "id": "hero",
                    "classes": ["hero-section"],
                    "styles": {"width": "100%", "fontSize": "20px"},
                    "children": [],
                }
            }
        }
        rules = mvc._extract_responsive_rules(viewports_data)
        self.assertTrue(len(rules) >= 2)
        mqs = [r["media_query"] for r in rules]
        self.assertIn("@media (max-width: 768px)", mqs)
        rule_hero = next(r for r in rules if r["selector"] == "#hero" and r["media_query"] == "@media (max-width: 768px)")
        self.assertEqual(rule_hero["diffs"]["width"]["target"], "100%")


if __name__ == "__main__":
    unittest.main()

