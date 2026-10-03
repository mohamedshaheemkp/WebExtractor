from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from webextractor.generator.project import ReactProjectGenerator


class TestPhase5NavigationOverlay(unittest.TestCase):
    def test_navigation_overlay_generated_and_wired(self):
        """Proves NavigationOverlay renders captured links, social items, and is wired into layout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            site_ir = {
                "metadata": {"title": "Overlay Test"},
                "routes": ["/", "/work", "/designs", "/motion", "/contact"],
                "design_system": {},
                "pages": [{"route": "/", "components": []}],
            }

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            overlay_file = out_path / "components/NavigationOverlay.tsx"
            self.assertTrue(overlay_file.exists())
            code = overlay_file.read_text(encoding="utf-8")

            # Route navigation links
            self.assertIn('"Home"', code)
            self.assertIn('"Work"', code)
            self.assertIn('"DESIGNS"', code)
            self.assertIn('"MOTION"', code)
            self.assertIn('"Contact"', code)

            # Social links
            self.assertIn('Instagram', code)
            self.assertIn('Dribbble', code)
            self.assertIn('Twitter', code)

            # Wiring to hamburger trigger
            self.assertIn('.framer-zecFa', code)
            self.assertIn('Escape', code)

            # Mounted in RootLayout
            layout_code = (out_path / "app/layout.tsx").read_text(encoding="utf-8")
            self.assertIn('<NavigationOverlay />', layout_code)
