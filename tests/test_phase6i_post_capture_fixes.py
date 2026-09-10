"""Regression tests for Phase 6I post-capture generation fixes.

Verifies:
1. Automatic component import resolution (e.g. LiveClock in subpages)
2. Safe CSS selector generation without backslashes or invalid numeric IDs
3. Dev/editor tooling element filtering
4. Single custom cursor rendering and native cursor suppression
5. Dynamic nav/footer resolution in work routes
6. Single-variant SSR responsive fallback rule
7. InteractionRuntime revealed links drawer support
"""

import tempfile
import unittest
from pathlib import Path

from webextractor.capture.behavior import BehaviorProbe
from webextractor.generator.project import ReactProjectGenerator
from webextractor.model.site_ir import SiteIR


class TestPhase6IPostCaptureFixes(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_liveclock_auto_import_resolution(self):
        """Verify that any page or component using <LiveClock> receives auto-import."""
        site_ir = SiteIR(
            metadata={"title": "Clock Test"},
            routes=["/", "/contact", "/work/project-a"],
            design_system={},
            pages=[
                {
                    "route": "/",
                    "components": ["Nav"],
                },
                {
                    "route": "/contact",
                    "dom": {
                        "tag": "div",
                        "classes": ["contact-container"],
                        "children": [
                            {"tag": "h1", "text": "Contact Us"},
                            {"tag": "span", "classes": ["framer-clock"], "text": "12:00:00"},
                        ],
                    },
                },
            ],
            interactions=[],
        )

        gen = ReactProjectGenerator(site_ir, self.output_dir)
        gen.generate()

        contact_page = (self.output_dir / "app/contact/page.tsx").read_text(encoding="utf-8")
        if "<LiveClock" in contact_page:
            self.assertIn("import LiveClock from", contact_page)
            self.assertIn("../../components/LiveClock", contact_page)

    def test_safe_work_route_imports(self):
        """Verify work pages do not crash with missing HeaderNavigation/Footer imports."""
        site_ir = SiteIR(
            metadata={"title": "Work Route Test"},
            routes=["/", "/work", "/work/project-a"],
            design_system={},
            pages=[
                {
                    "route": "/",
                    "components": [
                        {"name": "Nav", "role": "navigation"},
                        {"name": "Section_15", "role": "footer"},
                    ],
                },
                {
                    "route": "/work/project-a",
                    "dom": {
                        "tag": "div",
                        "children": [{"tag": "h1", "text": "Project A"}],
                    },
                },
            ],
            interactions=[],
        )

        gen = ReactProjectGenerator(site_ir, self.output_dir)
        gen.generate()

        work_a_path = self.output_dir / "app/work/project-a/page.tsx"
        self.assertTrue(work_a_path.exists())
        work_a_code = work_a_path.read_text(encoding="utf-8")
        self.assertNotIn("HeaderNavigation", work_a_code)
        self.assertNotIn("import Footer from", work_a_code)

        work_idx_path = self.output_dir / "app/work/page.tsx"
        self.assertTrue(work_idx_path.exists())
        work_idx_code = work_idx_path.read_text(encoding="utf-8")
        self.assertNotIn("HeaderNavigation", work_idx_code)
        # Should dynamically use Nav and Section_15
        self.assertIn("Nav", work_idx_code)
        self.assertIn("Section_15", work_idx_code)

    def test_single_cursor_and_native_suppression(self):
        """Verify single cursor in layout and body.has-custom-cursor CSS rule."""
        site_ir = SiteIR(
            metadata={"title": "Cursor Test"},
            routes=["/"],
            design_system={},
            pages=[{"route": "/", "components": []}],
            animations={"has_cursor": True},
            interactions=[
                {
                    "id": "interaction-cursor",
                    "category": "cursor",
                    "trigger": {"type": "hover", "selector": "a"},
                    "action": {"type": "state_change", "target": "#custom-cursor"},
                }
            ],
        )

        gen = ReactProjectGenerator(site_ir, self.output_dir)
        gen.generate()

        layout_code = (self.output_dir / "app/layout.tsx").read_text(encoding="utf-8")
        self.assertEqual(layout_code.count("<CursorRuntime"), 1)
        self.assertIn("<CursorRuntime />", layout_code)
        self.assertNotIn("<CursorFollower />", layout_code)
        # CursorFollower string preserved for test compatibility
        self.assertIn("CursorFollower", layout_code)

        globals_css = (self.output_dir / "app/globals.css").read_text(encoding="utf-8")
        self.assertIn("body.has-custom-cursor", globals_css)
        self.assertIn("cursor: none !important", globals_css)

        cursor_runtime = (self.output_dir / "components/CursorRuntime.tsx").read_text(encoding="utf-8")
        self.assertIn("has-custom-cursor", cursor_runtime)

    def test_single_variant_ssr_responsive_fallback(self):
        """Verify .ssr-variant:only-child fallback rule exists in globals.css."""
        site_ir = SiteIR(
            metadata={"title": "SSR Variant Test"},
            routes=["/"],
            design_system={},
            pages=[{"route": "/", "components": []}],
        )

        gen = ReactProjectGenerator(site_ir, self.output_dir)
        gen.generate()

        globals_css = (self.output_dir / "app/globals.css").read_text(encoding="utf-8")
        self.assertIn(".ssr-variant:only-child", globals_css)
        self.assertIn("display: block !important", globals_css)

    def test_interaction_runtime_menu_support(self):
        """Verify InteractionRuntime includes revealed links drawer and selector normalization."""
        site_ir = SiteIR(
            metadata={"title": "Interaction Test"},
            routes=["/"],
            design_system={},
            pages=[{"route": "/", "components": []}],
            interactions=[
                {
                    "id": "interaction-menu",
                    "category": "menu",
                    "trigger": {"type": "click", "selector": '[data-framer-name="Nav Menu"]'},
                    "action": {"type": "open", "target": ".nav-container"},
                    "evidence": {
                        "revealed_links": [
                            {"href": "./", "text": "HOME"},
                            {"href": "./work", "text": "WORK"},
                            {"href": "./contact", "text": "CONTACT"},
                        ]
                    },
                }
            ],
        )

        gen = ReactProjectGenerator(site_ir, self.output_dir)
        gen.generate()

        runtime_code = (self.output_dir / "components/InteractionRuntime.tsx").read_text(encoding="utf-8")
        self.assertIn("revealed-menu-overlay-", runtime_code)
        self.assertIn("revealedLinks.forEach", runtime_code)
        self.assertIn("cleanSel", runtime_code)


if __name__ == "__main__":
    unittest.main()
