from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from webextractor.generator.project import ReactProjectGenerator


class TestPhase3NoSyntheticFabrication(unittest.TestCase):
    def test_captured_work_generated_from_source_dom(self):
        """Proves captured /work page is generated from authentic DOM, never synthetic fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            site_ir = {
                "metadata": {"title": "Real Work Site"},
                "routes": ["/", "/work"],
                "design_system": {},
                "pages": [
                    {
                        "route": "/",
                        "components": ["Hero"],
                        "dom": {"tag": "div", "children": [{"tag": "h1", "text": "Home"}]},
                    },
                    {
                        "route": "/work",
                        "dom": {
                            "tag": "main",
                            "classes": ["framer-authentic-work-page"],
                            "children": [
                                {"tag": "h1", "text": "Authentic Work Portfolio"},
                                {"tag": "div", "text": "Real captured client work"},
                            ],
                        },
                    },
                ],
                "data": {
                    "projects": [
                        {"slug": "fake-proj", "title": "Fake Project", "category": "Fake"}
                    ]
                },
            }

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            work_file = out_path / "app/work/page.tsx"
            self.assertTrue(work_file.exists())
            code = work_file.read_text(encoding="utf-8")

            # Must contain authentic DOM content
            self.assertIn("Authentic Work Portfolio", code)
            self.assertIn("framer-authentic-work-page", code)
            # Must NOT use synthetic scaffold copy
            self.assertNotIn("// PORTFOLIO", code)
            self.assertNotIn("Selected Work", code)

    def test_captured_work_subroute_generated_from_source_dom(self):
        """Proves captured /work/:slug is generated from authentic DOM, not synthetic fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            site_ir = {
                "metadata": {"title": "Subroute Site"},
                "routes": ["/", "/work/agriai"],
                "design_system": {},
                "pages": [
                    {
                        "route": "/work/agriai",
                        "dom": {
                            "tag": "article",
                            "classes": ["framer-agriai-case-study"],
                            "children": [
                                {"tag": "h1", "text": "AgriAI Intelligent System"},
                            ],
                        },
                    },
                ],
            }

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            agriai_file = out_path / "app/work/agriai/page.tsx"
            self.assertTrue(agriai_file.exists())
            code = agriai_file.read_text(encoding="utf-8")

            self.assertIn("AgriAI Intelligent System", code)
            self.assertIn("framer-agriai-case-study", code)
            # Must not have synthetic fallback
            self.assertNotIn("← Back to Overview", code)
            self.assertNotIn("Pipeline Notice", code)

    def test_missing_route_reports_pipeline_error_notice(self):
        """Proves missing captured route produces an honest error notice, never a fake page."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            site_ir = {
                "metadata": {"title": "Missing Route Test"},
                "routes": ["/", "/work"],
                "design_system": {},
                "pages": [
                    {
                        "route": "/",
                        "components": ["Hero"],
                        "dom": {"tag": "div", "children": [{"tag": "h1", "text": "Home"}]},
                    }
                    # /work intentionally NOT in pages
                ],
            }

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            work_file = out_path / "app/work/page.tsx"
            self.assertTrue(work_file.exists())
            code = work_file.read_text(encoding="utf-8")

            self.assertIn("Pipeline Notice: Route /work was not captured from source evidence", code)
            self.assertNotIn("Selected Work", code)
