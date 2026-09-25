import tempfile
import unittest
from pathlib import Path

from webextractor.capture.multi_viewport import MultiViewportCapture
from webextractor.constants import DEFAULT_VIEWPORTS


class TestMultiViewports(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_viewports_have_five_breakpoints(self):
        """Validates that DEFAULT_VIEWPORTS contains 375, 768, 1024, 1440, and 1920."""
        self.assertIn("mobile", DEFAULT_VIEWPORTS)
        self.assertIn("tablet", DEFAULT_VIEWPORTS)
        self.assertIn("laptop", DEFAULT_VIEWPORTS)
        self.assertIn("desktop", DEFAULT_VIEWPORTS)
        self.assertIn("widescreen", DEFAULT_VIEWPORTS)

        self.assertEqual(DEFAULT_VIEWPORTS["mobile"]["width"], 375)
        self.assertEqual(DEFAULT_VIEWPORTS["tablet"]["width"], 768)
        self.assertEqual(DEFAULT_VIEWPORTS["laptop"]["width"], 1024)
        self.assertEqual(DEFAULT_VIEWPORTS["desktop"]["width"], 1440)
        self.assertEqual(DEFAULT_VIEWPORTS["widescreen"]["width"], 1920)

    def test_custom_viewports_initialization(self):
        """Validates that MultiViewportCapture accepts custom viewport definitions."""
        custom_vps = {
            "phone": {"width": 320, "height": 568},
            "ultrawide": {"width": 2560, "height": 1440},
        }
        capture = MultiViewportCapture(self.out_path, viewports=custom_vps)
        self.assertEqual(capture.viewports, custom_vps)

    def test_responsive_rule_extraction_logic(self):
        """Validates that differential style changes between desktop and mobile are extracted."""
        capture = MultiViewportCapture(self.out_path)
        viewports_data = {
            "desktop": {
                "dom": {
                    "tag": "section",
                    "id": "hero",
                    "classes": ["hero-banner"],
                    "text": "Hero Section",
                    "styles": {
                        "display": "flex",
                        "fontSize": "48px",
                        "flexDirection": "row",
                        "padding": "80px 40px",
                    },
                    "children": [],
                }
            },
            "mobile": {
                "dom": {
                    "tag": "section",
                    "id": "hero",
                    "classes": ["hero-banner"],
                    "text": "Hero Section",
                    "styles": {
                        "display": "block",
                        "fontSize": "28px",
                        "flexDirection": "column",
                        "padding": "40px 16px",
                    },
                    "children": [],
                }
            },
        }

        rules = capture._extract_responsive_rules(viewports_data)
        self.assertTrue(len(rules) > 0)
        hero_rule = rules[0]
        self.assertIn("fontSize", hero_rule["diffs"])
        self.assertEqual(hero_rule["diffs"]["fontSize"]["desktop"], "48px")
        self.assertEqual(hero_rule["diffs"]["fontSize"]["mobile"], "28px")
        self.assertEqual(hero_rule["diffs"]["flexDirection"]["desktop"], "row")
        self.assertEqual(hero_rule["diffs"]["flexDirection"]["mobile"], "column")


if __name__ == "__main__":
    unittest.main()
