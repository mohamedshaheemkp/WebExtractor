import tempfile
import unittest
from pathlib import Path

from webextractor.generator.static import StaticProjectGenerator


class TestStaticGenerator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_path = Path(self.temp_dir.name)

        self.mock_ir = {
            "metadata": {
                "title": "Static Demo Website",
                "url": "https://example.com",
            },
            "routes": ["/", "/about"],
            "design_system": {
                "colors": {"background": "#111111", "foreground": "#ffffff", "primary": "#0070f3"},
                "radii": {"card": "12px"},
            },
            "typography": {
                "font_families": [{"name": "Inter", "fallbacks": ["sans-serif"]}],
                "roles": {"heading": {"font_size": "32px", "font_weight": "700"}},
            },
            "layout": {
                "tokens": {"container_max_width": "1200px", "container_padding": "60px 24px"},
            },
            "pages": [
                {
                    "route": "/",
                    "title": "Home",
                    "dom": {
                        "tag": "main",
                        "classes": ["hero-section"],
                        "children": [
                            {"tag": "h1", "text": "Welcome to WebExtractor", "children": []},
                            {"tag": "p", "text": "High fidelity static reconstruction.", "children": []},
                            {"tag": "img", "attributes": {"src": "/images/logo.png", "alt": "Logo"}, "children": []},
                        ],
                    },
                },
                {
                    "route": "/about",
                    "title": "About Us",
                    "dom": {
                        "tag": "section",
                        "classes": ["about-section"],
                        "children": [
                            {"tag": "h2", "text": "About WebExtractor", "children": []},
                        ],
                    },
                },
            ],
            "asset_bindings": [
                {
                    "source_url": "https://example.com/logo.png",
                    "local_path": "/images/logo.png",
                    "role": "image",
                }
            ],
            "component_styles": {},
            "animations": {},
            "interactions": [],
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_static_generation_structure(self):
        """Validates that StaticProjectGenerator produces zero-dependency static assets."""
        generator = StaticProjectGenerator(self.mock_ir, self.out_path)
        generator.generate()

        # Check files exist
        self.assertTrue((self.out_path / "index.html").exists())
        self.assertTrue((self.out_path / "about.html").exists())
        self.assertTrue((self.out_path / "css" / "tokens.css").exists())
        self.assertTrue((self.out_path / "css" / "styles.css").exists())
        self.assertTrue((self.out_path / "js" / "app.js").exists())
        self.assertTrue((self.out_path / "README.md").exists())

        # Validate index.html contents
        index_html = (self.out_path / "index.html").read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", index_html)
        self.assertIn("<title>Home</title>", index_html)
        self.assertIn("Welcome to WebExtractor", index_html)
        self.assertIn("High fidelity static reconstruction.", index_html)
        self.assertIn('src="assets/images/logo.png"', index_html)
        self.assertIn('href="./css/tokens.css"', index_html)
        self.assertIn('src="./js/app.js"', index_html)

        # Validate about.html contents
        about_html = (self.out_path / "about.html").read_text(encoding="utf-8")
        self.assertIn("<title>About Us</title>", about_html)
        self.assertIn("About WebExtractor", about_html)

        # Validate tokens.css contents
        tokens_css = (self.out_path / "css" / "tokens.css").read_text(encoding="utf-8")
        self.assertIn("--color-background: #111111;", tokens_css)
        self.assertIn("--container-max-width: 1200px;", tokens_css)

        # Validate app.js contents
        app_js = (self.out_path / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("IntersectionObserver", app_js)
        self.assertIn("Parallax", app_js)

    def test_parallax_motion_and_clean_transform(self):
        """Validates that parallax elements are wired into app.js and resting transform: none is stripped."""
        custom_ir = dict(self.mock_ir)
        custom_ir["animations"] = {"parallax_elements": [".framer-1f6tfe0"]}
        custom_ir["pages"] = [
            {
                "route": "/",
                "title": "Home",
                "dom": {
                    "tag": "div",
                    "classes": ["framer-1f6tfe0"],
                    "attributes": {
                        "style": "will-change: transform; opacity: 1; transform: none;",
                        "data-framer-name": "Fill Your Image Here",
                    },
                    "children": [],
                },
            }
        ]

        generator = StaticProjectGenerator(custom_ir, self.out_path)
        generator.generate()

        index_html = (self.out_path / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("transform: none", index_html)
        self.assertIn("will-change: transform", index_html)

        app_js = (self.out_path / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn(".framer-1f6tfe0", app_js)
        self.assertIn("data-parallax-speed", app_js)

    def test_continuous_marquee_motion_script_emission(self):
        """Validates that generic continuous horizontal motion / marquee runtime is emitted in app.js."""
        generator = StaticProjectGenerator(self.mock_ir, self.out_path)
        generator.generate()

        app_js = (self.out_path / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Continuous Horizontal Motion / Marquee Runtime", app_js)
        self.assertIn("data-continuous-motion", app_js)
        self.assertIn("track.animate", app_js)
        self.assertIn("translateX", app_js)


if __name__ == "__main__":
    unittest.main()
