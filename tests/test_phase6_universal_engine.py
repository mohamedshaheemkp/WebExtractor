from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.analysis.layout import LayoutAnalyzer
from webextractor.analysis.motion_adapters.framer import FramerMotionAdapter
from webextractor.analysis.motion_adapters.standard import StandardCssMotionAdapter
from webextractor.analysis.source_css import extract_relevant_css
from webextractor.capture.crawler import WebsiteCrawler
from webextractor.generator.dom_emitter import DomToJsxEmitter
from webextractor.generator.project import ReactProjectGenerator
from webextractor.model.site_ir import SiteIR


class TestPhase6UniversalEngine(unittest.TestCase):
    """
    Comprehensive test suite validating the 12 key criteria of
    Phase 6: Universal Reconstruction Engine.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. Multi-route discovery
    def test_01_multi_route_discovery(self):
        crawler = WebsiteCrawler(self.output_dir, max_routes=5, same_origin=True)
        base = "https://universal-example.org"

        links = [
            "/about",
            "/contact",
            "/services/web-dev",
            "https://universal-example.org/blog",
            "./pricing",
        ]

        discovered = []
        for l in links:
            res = crawler.normalize_route(l, base)
            if res:
                discovered.append(res[0])

        self.assertIn("/about", discovered)
        self.assertIn("/contact", discovered)
        self.assertIn("/services/web-dev", discovered)
        self.assertIn("/blog", discovered)
        self.assertIn("/pricing", discovered)

    # 2. Route deduplication
    def test_02_route_deduplication(self):
        crawler = WebsiteCrawler(self.output_dir, same_origin=True)
        base = "https://universal-example.org"

        variations = [
            "/about",
            "/about/",
            "/about#team",
            "/about#history",
            "https://universal-example.org/about",
            "https://universal-example.org/about/",
        ]

        routes = set()
        for v in variations:
            norm = crawler.normalize_route(v, base)
            if norm:
                routes.add(norm[0])

        self.assertEqual(len(routes), 1)
        self.assertEqual(list(routes)[0], "/about")

    # 3. Same-origin filtering
    def test_03_same_origin_filtering(self):
        crawler = WebsiteCrawler(self.output_dir, same_origin=True)
        base = "https://universal-example.org"

        disallowed = [
            "https://external-platform.com/feature",
            "http://other-domain.net/about",
            "mailto:contact@universal-example.org",
            "tel:+1234567890",
            "javascript:void(0)",
            "data:text/html,hello",
            "/downloads/catalog.pdf",
            "/assets/bundle.js",
            "/styles/theme.css",
            "/images/logo.png",
        ]

        for link in disallowed:
            res = crawler.normalize_route(link, base)
            self.assertIsNone(res, f"Expected {link} to be filtered out")

    # 4. CSS preservation
    def test_04_css_preservation(self):
        sample_css = """
        :root { --brand-primary: #0066cc; --spacing-unit: 8px; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .hero-title { font-family: 'Inter', sans-serif; font-size: 48px; color: var(--brand-primary); }
        .unused-class { display: none; }
        @media (max-width: 768px) {
            .hero-title { font-size: 32px; }
            .unused-class { display: block; }
        }
        """
        res = extract_relevant_css(
            html_content="",
            referenced_classes={"hero-title"},
            external_css=sample_css,
        )

        class_rules_str = "\n".join(res["class_rules"])
        media_rules_str = "\n".join(res["media_rules"])
        keyframes_str = "\n".join(res.get("keyframes", []))

        self.assertIn("hero-title", class_rules_str)
        self.assertIn("var(--brand-primary)", class_rules_str)
        self.assertNotIn("unused-class", class_rules_str)
        self.assertIn("@media (max-width: 768px)", media_rules_str)
        self.assertIn("fadeIn", keyframes_str)

    # 5. Transient animation-state removal
    def test_05_transient_animation_state_removal(self):
        emitter = DomToJsxEmitter(motion_targets={"anim-target-1"})

        # Transient motion element: initial opacity 0 and translateY
        motion_node = {
            "tag": "div",
            "id": "anim-target-1",
            "classes": ["fade-element"],
            "attributes": {
                "id": "anim-target-1",
                "style": "opacity: 0; transform: translateY(40px); will-change: transform; color: #fff;",
            },
            "children": [],
            "text": "Animated Content",
        }
        jsx_motion = emitter.emit_jsx(motion_node)

        self.assertIn('data-motion-id="anim-target-1"', jsx_motion)
        # Transient opacity: 0 and transform: translateY should be suppressed
        self.assertNotIn('opacity: "0"', jsx_motion)
        self.assertNotIn('translateY', jsx_motion)
        # Truthful static color should remain
        self.assertIn('color: "#fff"', jsx_motion)

        # Static element: centering transform should be preserved
        static_node = {
            "tag": "div",
            "id": "static-centered",
            "classes": ["centered-badge"],
            "attributes": {
                "id": "static-centered",
                "style": "position: absolute; transform: translate(-50%, -50%); color: #333;",
            },
            "children": [],
            "text": "Centered",
        }
        jsx_static = emitter.emit_jsx(static_node)
        self.assertIn("translate(-50%, -50%)", jsx_static)
        self.assertIn('color: "#333"', jsx_static)

    # 6. Responsive CSS
    def test_06_responsive_css(self):
        css = """
        @media (max-width: 1280px) { .container { max-width: 1200px; } }
        @media (max-width: 1024px) { .nav { display: none; } }
        @media (max-width: 640px) { .hero { font-size: 24px; } }
        display: flex;
        display: grid;
        """
        analysis = LayoutAnalyzer.analyze(css)
        inferred = analysis.get("inferred_breakpoints", [])

        self.assertIn(1280, inferred)
        self.assertIn(1024, inferred)
        self.assertIn(640, inferred)
        self.assertTrue(analysis["uses_flex"])
        self.assertTrue(analysis["uses_grid"])

    # 7. Normalized motion
    def test_07_normalized_motion(self):
        site_ir = SiteIR(
            metadata={"title": "Universal Motion Demo"},
            routes=["/"],
            design_system={},
            animations={
                "appear_animations": {
                    "card-1": {
                        "initial": {"opacity": 0, "y": 30},
                        "animate": {"opacity": 1, "y": 0},
                        "transition": {"type": "spring", "stiffness": 260, "damping": 30},
                    }
                },
                "motion_triggers": [
                    {"type": "in_view", "target_selector": "#card-1", "once": True}
                ],
                "parallax_elements": [".parallax-hero"],
            },
        )
        gen = ReactProjectGenerator(site_ir, self.output_dir)
        gen.generate()

        runtime_code = (self.output_dir / "components/MotionRuntime.tsx").read_text(encoding="utf-8")
        self.assertIn("IntersectionObserver", runtime_code)
        self.assertIn("pointerenter", runtime_code)
        self.assertIn("pointerdown", runtime_code)
        self.assertIn("window.requestAnimationFrame", runtime_code)
        self.assertIn("data-toggle-target", runtime_code)
        self.assertNotIn("framer-motion", runtime_code)

    # 8. Generic non-Framer HTML
    def test_08_generic_non_framer_html(self):
        html = """<!DOCTYPE html>
        <html>
        <head><title>WordPress / Custom Site</title></head>
        <body>
          <header class="wp-site-header">
            <nav><a href="/">Home</a><a href="/about">About</a></nav>
          </header>
          <main class="wp-site-main">
            <section class="wp-hero"><h1>Custom Modern Site</h1><p>Fast and clean.</p></section>
          </main>
          <footer class="wp-site-footer"><p>&copy; 2026 Acme Corp</p></footer>
        </body>
        </html>"""

        analyzer = SiteAnalyzer()
        capture = {
            "url": "https://acme-corp.com",
            "html": html,
            "dom": {
                "tag": "body",
                "children": [
                    {"tag": "header", "classes": ["wp-site-header"], "text": "Home About", "children": []},
                    {"tag": "section", "classes": ["wp-hero"], "text": "Custom Modern Site", "children": []},
                    {"tag": "footer", "classes": ["wp-site-footer"], "text": "Acme Corp", "children": []},
                ],
            },
            "requests": [],
            "viewports": {},
        }
        site_model = analyzer.analyze(capture)
        self.assertEqual(site_model.title, "WordPress / Custom Site")
        self.assertIn("/", site_model.routes)

    # 9. Framer HTML through FramerMotionAdapter
    def test_09_framer_html_through_framer_motion_adapter(self):
        framer_html = """
        <div data-framer-appear-id="appear-abc" style="opacity:0.001; transform:translateY(20px);">
            <span>Framer Motion Card</span>
        </div>
        """
        adapter = FramerMotionAdapter()
        self.assertTrue(adapter.can_handle(framer_html))

        extracted = adapter.extract_motion(framer_html)
        self.assertIn("appear-abc", extracted["appear_animations"])
        config = extracted["appear_animations"]["appear-abc"]
        self.assertEqual(config["initial"]["opacity"], 0)
        self.assertEqual(config["animate"]["opacity"], 1)

    # 10. CSS animation through StandardCssMotionAdapter
    def test_10_css_animation_through_standard_css_motion_adapter(self):
        css = """
        @keyframes pulseGlow {
            0% { transform: scale(1); opacity: 0.8; }
            50% { transform: scale(1.05); opacity: 1; }
            100% { transform: scale(1); opacity: 0.8; }
        }
        .pulse-card {
            animation: pulseGlow 2s infinite ease-in-out;
        }
        """
        html = '<div class="pulse-card">Glowing card</div>'
        adapter = StandardCssMotionAdapter()
        self.assertTrue(adapter.can_handle(html, css))

        res = adapter.extract_motion(html, css)
        self.assertTrue(len(res["keyframes"]) > 0)
        self.assertEqual(res["keyframes"][0]["name"], "pulseGlow")

    # 11. Route reconstruction
    def test_11_route_reconstruction(self):
        site_ir = SiteIR(
            metadata={"title": "Multi-Route Reconstructed App"},
            routes=["/", "/about", "/contact"],
            design_system={},
            pages=[
                {
                    "route": "/",
                    "title": "Home",
                    "dom": {"tag": "div", "text": "Welcome to Homepage", "children": []},
                    "components": ["HeaderNavigation", "Hero", "Footer"],
                },
                {
                    "route": "/about",
                    "title": "About Us",
                    "dom": {
                        "tag": "section",
                        "classes": ["about-page-content"],
                        "text": "Truthful Captured About Content",
                        "children": [
                            {"tag": "h1", "text": "Our Vision and Mission", "children": []}
                        ],
                    },
                },
                {
                    "route": "/contact",
                    "title": "Contact",
                    "dom": {
                        "tag": "section",
                        "classes": ["contact-page-content"],
                        "text": "Truthful Captured Contact Information",
                        "children": [
                            {"tag": "h1", "text": "Get In Touch Directly", "children": []}
                        ],
                    },
                },
            ],
        )

        gen = ReactProjectGenerator(site_ir, self.output_dir)
        gen.generate()

        about_file = self.output_dir / "app/about/page.tsx"
        contact_file = self.output_dir / "app/contact/page.tsx"

        self.assertTrue(about_file.exists())
        self.assertTrue(contact_file.exists())

        about_code = about_file.read_text(encoding="utf-8")
        contact_code = contact_file.read_text(encoding="utf-8")

        self.assertIn("Our Vision and Mission", about_code)
        self.assertIn("Get In Touch Directly", contact_code)

    # 12. No hardcoded portfolio content
    def test_12_no_hardcoded_portfolio_content(self):
        generator_dir = Path(__file__).resolve().parent.parent / "src/webextractor/generator"

        forbidden_portfolio_phrases = [
            "more about shaheem",
            "voice of ms",
            "based in india",
            "mhd_shm",
            "available for innovative projects worldwide",
            "let's build together",
        ]

        for py_file in generator_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8").lower()
            for phrase in forbidden_portfolio_phrases:
                self.assertNotIn(
                    phrase,
                    content,
                    f"Forbidden hardcoded portfolio phrase '{phrase}' found in {py_file.name}",
                )


if __name__ == "__main__":
    unittest.main()
