"""
Tests for Stage 3: Responsive Generation Fidelity.
Verifies that responsive rules are extracted, preserved through IR, and emitted as @media rules
without relying on overflow-x: hidden.
"""
import unittest
from pathlib import Path
import tempfile
import shutil

from webextractor.capture.multi_viewport import MultiViewportCapture
from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.model.site_ir import SiteIR
from webextractor.generator.static import StaticProjectGenerator
from webextractor.generator.project import ReactProjectGenerator


class TestResponsiveGenerationFidelity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.output_path = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_responsive_rules_safe_selectors_and_no_bare_tags(self):
        """Verifies that multi-tier matching uses safe selectors and avoids bare div tags."""
        mvc = MultiViewportCapture(output_dir="")
        viewports_data = {
            "vp_1440": {
                "viewport": {"width": 1440, "height": 900},
                "dom": {
                    "tag": "div",
                    "path": "0",
                    "framerAppearId": "appear-hero",
                    "framerName": "HeroBanner",
                    "styles": {"width": "1200px", "padding": "40px 80px"},
                    "children": [
                        {
                            "tag": "div",
                            "path": "0_0",
                            "classes": ["hero-title"],
                            "styles": {"fontSize": "64px"},
                            "children": [],
                        },
                        {
                            "tag": "div",
                            "path": "0_1",
                            "styles": {"width": "500px"},
                            "children": [],
                        }
                    ]
                }
            },
            "vp_375": {
                "viewport": {"width": 375, "height": 812},
                "dom": {
                    "tag": "div",
                    "path": "0",
                    "framerAppearId": "appear-hero",
                    "framerName": "HeroBanner",
                    "styles": {"width": "100%", "padding": "20px 16px"},
                    "children": [
                        {
                            "tag": "div",
                            "path": "0_0",
                            "classes": ["hero-title"],
                            "styles": {"fontSize": "32px"},
                            "children": [],
                        },
                        {
                            "tag": "div",
                            "path": "0_1",
                            "styles": {"width": "100%"},
                            "children": [],
                        }
                    ]
                }
            }
        }

        rules = mvc._extract_responsive_rules(viewports_data)
        self.assertTrue(len(rules) >= 2)
        selectors = [r["selector"] for r in rules]
        # Should contain [data-framer-appear-id='appear-hero'] and .hero-title
        self.assertIn("[data-framer-appear-id='appear-hero']", selectors)
        self.assertIn(".hero-title", selectors)
        # MUST NOT contain bare 'div'
        self.assertNotIn("div", selectors)

    def test_static_generator_emits_media_rules_and_no_body_overflow_hidden(self):
        """Verifies that static generator emits @media rules and does NOT force overflow-x: hidden on body."""
        ir = {
            "metadata": {"title": "Responsive Test"},
            "routes": ["/"],
            "design_system": {},
            "responsive_rules": [
                {
                    "selector": ".container-responsive",
                    "media_query": "@media (max-width: 768px)",
                    "breakpoint": "mobile",
                    "diffs": {"width": "100%", "padding": "16px"},
                }
            ],
            "component_styles": {
                "source_rules": {
                    "class_rules": [".container-responsive { width: 1200px; padding: 48px; }"],
                    "media_rules": [
                        "@media (max-width: 809.98px) {\n  .framer-nav { display: none; }\n}"
                    ],
                }
            },
            "pages": [{"route": "/", "title": "Home", "dom": {"tag": "div", "classes": ["container-responsive"], "children": []}}],
            "animations": {},
        }

        gen = StaticProjectGenerator(ir, self.output_path / "static")
        gen.generate()

        css_file = self.output_path / "static" / "css" / "styles.css"
        self.assertTrue(css_file.exists())
        css_content = css_file.read_text(encoding="utf-8")

        # 1. No body { overflow-x: hidden; }
        self.assertNotIn("body {\n  background: var(--color-background, #080808);\n  color: var(--color-foreground, #f5f5f5);\n  font-family: var(--font-body, system-ui, -apple-system, sans-serif);\n  line-height: 1.6;\n  overflow-x: hidden;", css_content)
        self.assertNotIn("overflow-x: hidden;", css_content)

        # 2. Contains responsive rules and source media rules
        self.assertIn("@media (max-width: 768px)", css_content)
        self.assertIn(".container-responsive", css_content)
        self.assertIn("width: 100% !important;", css_content)
        self.assertIn("@media (max-width: 809.98px)", css_content)
        self.assertIn(".framer-nav", css_content)

    def test_nextjs_generator_emits_media_rules(self):
        """Verifies that Next.js generator emits responsive rules and source media rules into globals.css."""
        ir = {
            "metadata": {"title": "Next Responsive Test"},
            "routes": ["/"],
            "design_system": {},
            "responsive_rules": [
                {
                    "selector": "[data-framer-appear-id='appear-hero']",
                    "media_query": "@media (max-width: 768px)",
                    "breakpoint": "mobile",
                    "diffs": {"width": "100%", "padding": "16px"},
                }
            ],
            "component_styles": {
                "source_rules": {
                    "media_rules": [
                        "@media (max-width: 809.98px) {\n  .framer-vGE5i { width: 390px; }\n}"
                    ],
                }
            },
            "pages": [{"route": "/", "title": "Home", "components": []}],
            "components": {"tag": "div", "children": []},
            "animations": {},
        }

        gen = ReactProjectGenerator(ir, self.output_path / "next")
        gen.generate()

        css_file = self.output_path / "next" / "app" / "globals.css"
        self.assertTrue(css_file.exists())
        css_content = css_file.read_text(encoding="utf-8")

        self.assertIn("@media (max-width: 768px)", css_content)
        self.assertIn("[data-framer-appear-id='appear-hero']", css_content)
        self.assertIn("width: 100% !important;", css_content)
        self.assertIn("@media (max-width: 809.98px)", css_content)
        self.assertIn(".framer-vGE5i", css_content)


if __name__ == "__main__":
    unittest.main()
