import json
import tempfile
import unittest
from pathlib import Path

from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.generator.project import ReactProjectGenerator
from webextractor.model.site_ir import SiteIR


class TestHardValidationPass(unittest.TestCase):

    def setUp(self):
        self.mock_capture = {
            "url": "https://origins.example.com",
            "html": """<!DOCTYPE html>
<html>
<head><title>Mohamed Shaheem — Principal Systems Engineer</title></head>
<body>
  <header class="header-nav"><a href="/">Origins</a></header>
  <section id="hero" class="hero-section">
    <h1>Mohamed Shaheem</h1>
    <p>Designing resilient, ultra-fast interfaces.</p>
  </section>
  <section id="intro">
    <h2>Welcome to Origins</h2>
  </section>
  <section id="projects" class="projects-section">
    <h2>Selected Projects</h2>
    <div class="project-card">WebExtractor Engine</div>
    <div class="project-card">Design Token Studio</div>
  </section>
  <section id="about">
    <h2>About Me</h2>
  </section>
  <section id="capabilities" class="capabilities-section">
    <h2>Capabilities</h2>
    <div class="capability-item">Interface Architecture</div>
    <div class="capability-item">Performance Optimization</div>
  </section>
  <section id="voice">
    <h2>Voice &amp; Testimonials</h2>
  </section>
  <section id="journey" class="journey-section">
    <h2>Journey</h2>
    <div class="journey-item">Lead Architect</div>
  </section>
  <section id="toolkit" class="toolkit-section">
    <h2>Toolkit</h2>
    <div class="toolkit-item">Next.js</div>
    <div class="toolkit-item">TypeScript</div>
  </section>
  <section id="contact">
    <h2>Get in Touch</h2>
  </section>
  <footer class="footer">
    <p>&copy; 2026 Mohamed Shaheem</p>
  </footer>
</body>
</html>""",
            "dom": {
                "tag": "body",
                "children": [
                    {"tag": "header", "classes": ["header-nav"], "text": "Origins Navigation", "children": []},
                    {"tag": "section", "id": "hero", "classes": ["hero-section"], "text": "Mohamed Shaheem", "styles": {"display": "flex", "padding": "100px 64px", "minHeight": "90vh"}, "children": []},
                    {"tag": "section", "id": "intro", "classes": ["intro-section"], "text": "Welcome to Origins", "children": []},
                    {"tag": "section", "id": "projects", "classes": ["projects-section"], "text": "Selected Projects", "children": [
                        {"tag": "div", "classes": ["project-card"], "text": "WebExtractor Engine", "children": []},
                        {"tag": "div", "classes": ["project-card"], "text": "Design Token Studio", "children": []},
                    ]},
                    {"tag": "section", "id": "about", "classes": ["about-section"], "text": "About Me", "children": []},
                    {"tag": "section", "id": "capabilities", "classes": ["capabilities-section"], "text": "Capabilities", "children": [
                        {"tag": "div", "classes": ["capability-item"], "text": "Interface Architecture", "children": []},
                    ]},
                    {"tag": "section", "id": "voice", "classes": ["voice-section"], "text": "Voice", "children": []},
                    {"tag": "section", "id": "journey", "classes": ["journey-section"], "text": "Journey", "children": [
                        {"tag": "div", "classes": ["journey-item"], "text": "Lead Architect", "children": []},
                    ]},
                    {"tag": "section", "id": "toolkit", "classes": ["toolkit-section"], "text": "Toolkit", "children": [
                        {"tag": "div", "classes": ["toolkit-item"], "text": "Next.js", "children": []},
                    ]},
                    {"tag": "section", "id": "contact", "classes": ["cta-section"], "text": "Get in Touch", "children": []},
                    {"tag": "footer", "classes": ["footer"], "text": "Footer", "children": []},
                ]
            },
            "viewports": {
                "desktop": {
                    "dom": {
                        "tag": "body",
                        "children": [
                            {"tag": "section", "id": "hero", "styles": {"display": "flex", "padding": "100px 64px", "minHeight": "90vh"}, "children": []},
                            {"tag": "section", "id": "projects", "styles": {"display": "flex", "padding": "100px 64px", "gap": "48px"}, "children": []},
                        ]
                    }
                },
                "mobile": {
                    "dom": {
                        "tag": "body",
                        "children": [
                            {"tag": "section", "id": "hero", "styles": {"display": "block", "padding": "60px 20px", "minHeight": "70vh"}, "children": []},
                            {"tag": "section", "id": "projects", "styles": {"display": "block", "padding": "40px 20px", "gap": "20px"}, "children": []},
                        ]
                    }
                }
            },
            "requests": [],
        }

    # ---------------------------------------------------------
    # 2. Validate IR Determinism
    # ---------------------------------------------------------
    def test_ir_determinism(self):
        """Validates that running the pipeline on the same source produces identical IR contracts."""
        analyzer_1 = SiteAnalyzer()
        site_1 = analyzer_1.analyze(self.mock_capture)
        ir_1 = SiteIR(
            metadata={"title": site_1.title, "url": site_1.url},
            routes=site_1.routes,
            design_system=getattr(site_1, "design_system", {}),
            pages=getattr(site_1, "pages", []),
            reusable_components=getattr(site_1, "reusable_components", []),
            component_styles=getattr(site_1, "component_styles", {}),
            data=getattr(site_1, "data", {}),
        ).to_dict()

        analyzer_2 = SiteAnalyzer()
        site_2 = analyzer_2.analyze(self.mock_capture)
        ir_2 = SiteIR(
            metadata={"title": site_2.title, "url": site_2.url},
            routes=site_2.routes,
            design_system=getattr(site_2, "design_system", {}),
            pages=getattr(site_2, "pages", []),
            reusable_components=getattr(site_2, "reusable_components", []),
            component_styles=getattr(site_2, "component_styles", {}),
            data=getattr(site_2, "data", {}),
        ).to_dict()

        # Both IR contracts must be 100% deterministic and identical
        self.assertEqual(json.dumps(ir_1, sort_keys=True), json.dumps(ir_2, sort_keys=True))

    # ---------------------------------------------------------
    # 3. Test Semantic Hierarchy in IR
    # ---------------------------------------------------------
    def test_semantic_hierarchy(self):
        """Validates that the IR explicitly models the full component hierarchy."""
        analyzer = SiteAnalyzer()
        site = analyzer.analyze(self.mock_capture)
        pages = getattr(site, "pages", [])

        self.assertTrue(len(pages) > 0)
        home_page = pages[0]
        self.assertEqual(home_page["route"], "/")

        comps = home_page["components"]
        comp_names = [c["name"] if isinstance(c, dict) else str(c) for c in comps]

        expected_hierarchy = [
            "HeaderNavigation",
            "Hero",
            "Intro",
            "Projects",
            "About",
            "Capabilities",
            "VoiceOfMS",
            "Journey",
            "Toolkit",
            "CTA",
            "Footer",
        ]

        self.assertEqual(comp_names, expected_hierarchy)

        # Check child relationships in IR
        projects_node = next(c for c in comps if c["name"] == "Projects")
        self.assertIn("ProjectCard", projects_node.get("children", []))
        self.assertEqual(projects_node.get("data_key"), "projects")

        cap_node = next(c for c in comps if c["name"] == "Capabilities")
        self.assertIn("CapabilityItem", cap_node.get("children", []))
        self.assertEqual(cap_node.get("data_key"), "capabilities")

    # ---------------------------------------------------------
    # 4. Test Data / Component Separation
    # ---------------------------------------------------------
    def test_data_component_separation(self):
        """Validates that modifying data arrays does not break or require changing component code."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)
            analyzer = SiteAnalyzer()
            site = analyzer.analyze(self.mock_capture)
            site_ir = SiteIR(
                metadata={"title": site.title, "url": site.url},
                routes=site.routes,
                design_system=getattr(site, "design_system", {}),
                pages=getattr(site, "pages", []),
                reusable_components=getattr(site, "reusable_components", []),
                component_styles=getattr(site, "component_styles", {}),
                data=getattr(site, "data", {}),
            )

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            # Verify ProjectCard.tsx imports from ../data/projects and is decoupled
            card_code = (out_path / "components/ProjectCard.tsx").read_text(encoding="utf-8")
            self.assertIn('import { Project } from "../data/projects";', card_code)
            self.assertIn("project.title", card_code)

            # Verify projects.ts exports the typed interface and data array
            data_code = (out_path / "data/projects.ts").read_text(encoding="utf-8")
            self.assertIn("export type Project =", data_code)
            self.assertIn("export const projects: Project[] =", data_code)

    # ---------------------------------------------------------
    # 5. Check Responsive IR & Measured Style Observation
    # ---------------------------------------------------------
    def test_responsive_computed_style_observation(self):
        """Validates that component_styles contains real measured styles from Desktop & Mobile viewports."""
        analyzer = SiteAnalyzer()
        site = analyzer.analyze(self.mock_capture)
        comp_styles = getattr(site, "component_styles", {})

        self.assertIn("Hero", comp_styles)
        hero_desktop = comp_styles["Hero"]["desktop"]
        hero_mobile = comp_styles["Hero"]["mobile"]

        # Measured from desktop DOM
        self.assertEqual(hero_desktop.get("display"), "flex")
        self.assertEqual(hero_desktop.get("padding"), "100px 64px")

        # Measured from mobile DOM
        self.assertEqual(hero_mobile.get("display"), "block")
        self.assertEqual(hero_mobile.get("padding"), "60px 20px")


if __name__ == "__main__":
    unittest.main()
