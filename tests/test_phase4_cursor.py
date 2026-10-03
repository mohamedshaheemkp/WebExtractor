from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from webextractor.generator.project import ReactProjectGenerator


class TestPhase4Cursor(unittest.TestCase):
    def test_cursor_runtime_desktop_guard_and_blend_mode(self):
        """Proves CursorRuntime adheres to fine-pointer guard, difference blend mode, and RAF positioning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            site_ir = {
                "metadata": {"title": "Cursor Test"},
                "routes": ["/"],
                "design_system": {},
                "pages": [{"route": "/", "components": []}],
                "animations": {"has_cursor": True},
            }

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            cursor_file = out_path / "components/CursorRuntime.tsx"
            self.assertTrue(cursor_file.exists())
            code = cursor_file.read_text(encoding="utf-8")

            # 1. Desktop fine-pointer guard
            self.assertIn('(hover: hover) and (pointer: fine)', code)
            # 2. Difference blend mode
            self.assertIn('difference', code)
            # 3. Direct DOM positioning (requestAnimationFrame, no React setState on mousemove)
            self.assertIn('requestAnimationFrame', code)
            self.assertNotIn('setPos(', code)
            # 4. Resting size 16px
            self.assertIn('width: 16', code)
            self.assertIn('height: 16', code)
            # 5. Hover target detection for data-framer-cursor
            self.assertIn('[data-framer-cursor]', code)
            self.assertIn('VIEW', code)

            # 6. Global CSS cursor suppression is guarded with @media (hover: hover) and (pointer: fine)
            globals_css = (out_path / "app/globals.css").read_text(encoding="utf-8")
            self.assertIn('@media (hover: hover) and (pointer: fine)', globals_css)
            self.assertIn('body.has-custom-cursor', globals_css)
            self.assertIn('cursor: none !important', globals_css)
