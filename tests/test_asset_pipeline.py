import tempfile
import unittest
from pathlib import Path

from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.assets.discovery import AssetDiscovery
from webextractor.generator.assets import AssetOrganizer
from webextractor.model.asset import Asset, AssetType


class TestAssetPipeline(unittest.TestCase):

    def test_discovery_from_crawler(self):
        capture = {
            "url": "https://example.com/portfolio",
            "requests": [
                {"url": "https://example.com/assets/hero.webp", "method": "GET", "resource_type": "image"},
                {"url": "https://example.com/fonts/inter.woff2", "method": "GET", "resource_type": "font"},
                {"url": "https://example.com/styles/main.css", "method": "GET", "resource_type": "stylesheet"},
            ],
            "html": """
            <html>
                <head>
                    <link rel="stylesheet" href="/styles/extra.css">
                </head>
                <body>
                    <img src="/images/project1.png" alt="Project 1">
                    <video src="/videos/intro.mp4" poster="/images/intro-poster.jpg"></video>
                </body>
            </html>
            """,
            "dom": {
                "tag": "body",
                "children": [
                    {
                        "tag": "div",
                        "styles": {
                            "backgroundImage": "url('https://example.com/bg/hero-bg.jpg')"
                        }
                    }
                ]
            }
        }

        assets = AssetDiscovery.from_crawler(capture, base_url="https://example.com")

        urls = {a.url for a in assets}
        self.assertIn("https://example.com/assets/hero.webp", urls)
        self.assertIn("https://example.com/fonts/inter.woff2", urls)
        self.assertIn("https://example.com/styles/main.css", urls)
        self.assertIn("https://example.com/styles/extra.css", urls)
        self.assertIn("https://example.com/images/project1.png", urls)
        self.assertIn("https://example.com/videos/intro.mp4", urls)
        self.assertIn("https://example.com/images/intro-poster.jpg", urls)
        self.assertIn("https://example.com/bg/hero-bg.jpg", urls)

        # Verify asset types
        types_by_url = {a.url: a.asset_type for a in assets}
        self.assertEqual(types_by_url["https://example.com/assets/hero.webp"], AssetType.IMAGE)
        self.assertEqual(types_by_url["https://example.com/fonts/inter.woff2"], AssetType.FONT)
        self.assertEqual(types_by_url["https://example.com/videos/intro.mp4"], AssetType.VIDEO)
        self.assertEqual(types_by_url["https://example.com/styles/main.css"], AssetType.CSS)

    def test_organizer_and_hard_invariant(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            cache_dir = project_dir / ".cache"
            cache_dir.mkdir(parents=True)

            # Create dummy downloaded files
            img_file = cache_dir / "hero.webp"
            img_file.write_bytes(b"dummy image bytes")

            font_file = cache_dir / "font.woff2"
            font_file.write_bytes(b"dummy font bytes")

            assets = [
                Asset(
                    url="https://example.com/hero.webp",
                    filename="hero.webp",
                    asset_type=AssetType.IMAGE,
                    downloaded=True,
                    local_path=img_file,
                    size=len(b"dummy image bytes"),
                ),
                Asset(
                    url="https://example.com/font.woff2",
                    filename="font.woff2",
                    asset_type=AssetType.FONT,
                    downloaded=True,
                    local_path=font_file,
                    size=len(b"dummy font bytes"),
                ),
                Asset(
                    url="https://example.com/failed.png",
                    filename="failed.png",
                    asset_type=AssetType.IMAGE,
                    downloaded=False,
                    local_path=None,
                ),
            ]

            manifest = AssetOrganizer.organize_assets(assets, project_dir)

            # Check public directory structure
            self.assertTrue((project_dir / "public" / "images" / "hero.webp").exists())
            self.assertTrue((project_dir / "public" / "fonts" / "font.woff2").exists())

            # Check updated Asset attributes
            downloaded_img = next(a for a in assets if a.url == "https://example.com/hero.webp")
            self.assertEqual(downloaded_img.local_path, project_dir / "public" / "images" / "hero.webp")
            self.assertEqual(downloaded_img.public_url, "/images/hero.webp")

            # Check manifest items
            manifest_by_src = {m["source"]: m for m in manifest}
            self.assertEqual(manifest_by_src["https://example.com/hero.webp"]["local"], "/images/hero.webp")
            self.assertTrue(manifest_by_src["https://example.com/hero.webp"]["downloaded"])
            self.assertIsNone(manifest_by_src["https://example.com/failed.png"]["local"])
            self.assertFalse(manifest_by_src["https://example.com/failed.png"]["downloaded"])

            # Check analysis/assets.json was written
            self.assertTrue((project_dir / "analysis" / "assets.json").exists())

    def test_analyzer_no_synthetic_paths(self):
        capture = {
            "url": "https://example.com",
            "html": "<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>",
            "dom": {"tag": "body", "children": []},
            "viewports": {},
            "requests": [],
        }

        # No downloaded assets
        assets = [
            Asset(
                url="https://example.com/image.png",
                filename="image.png",
                asset_type=AssetType.IMAGE,
                downloaded=False,
                local_path=None,
            )
        ]

        manifest = [
            {
                "source": "https://example.com/image.png",
                "local": None,
                "downloaded": False,
                "category": "images",
            }
        ]

        analyzer = SiteAnalyzer()
        site_model = analyzer.analyze(capture, assets=assets, asset_manifest=manifest)

        # Verify no fabricated /images/project-placeholder.webp exists
        data = getattr(site_model, "data", {})
        for proj in data.get("projects", []):
            self.assertIsNone(proj.get("image"))


if __name__ == "__main__":
    unittest.main()
