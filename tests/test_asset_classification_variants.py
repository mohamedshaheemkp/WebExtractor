"""
Tests for Stage 4, 5, and 6:
Asset Classification, Binding without Variant Overwrites, and Evidence-Backed Responsive Images.
"""
import unittest
from pathlib import Path
import tempfile
import shutil

from webextractor.model.asset import Asset, AssetType
from webextractor.har.normalizer import HARNormalizer
from webextractor.assets.organizer import AssetOrganizer
from webextractor.assets.downloader import AssetDownloader
from webextractor.assets.binding import AssetBindingEngine, ManifestLookup
from webextractor.generator.static import StaticProjectGenerator
from webextractor.generator.dom_emitter import DomToJsxEmitter


class TestAssetClassificationAndVariants(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.path = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_authoritative_mime_classification_over_extension(self):
        """MIME type must take precedence over misleading URL file extensions."""
        # 1. URL ends in .jpg, but MIME is text/javascript
        js_asset = HARNormalizer.classify_asset_type(
            "https://example.com/bundle.jpg", mime_type="text/javascript; charset=utf-8"
        )
        self.assertEqual(js_asset, AssetType.JAVASCRIPT)

        # 2. URL has no extension, MIME is image/png
        png_asset = HARNormalizer.classify_asset_type(
            "https://example.com/avatar", mime_type="image/png"
        )
        self.assertEqual(png_asset, AssetType.IMAGE)

        # 3. URL ends in .png, but MIME is text/html (e.g. error page)
        html_asset = HARNormalizer.classify_asset_type(
            "https://example.com/logo.png", mime_type="text/html"
        )
        self.assertEqual(html_asset, AssetType.HTML)

        # 4. Generic x-unknown MIME falls back to .webp extension
        webp_asset = HARNormalizer.classify_asset_type(
            "https://example.com/photo.webp", mime_type="x-unknown"
        )
        self.assertEqual(webp_asset, AssetType.IMAGE)

    def test_downloader_and_organizer_preserve_variants_without_collision(self):
        """Variants (@512, @1024, @2048) must not overwrite each other."""
        downloader = AssetDownloader(output_dir=self.path)

        a_512 = Asset(url="https://example.com/assets/images/image-fc98b695.jpg?scale-down-to=512&width=11760")
        a_1024 = Asset(url="https://example.com/assets/images/image-fc98b695.jpg?scale-down-to=1024&width=11760")
        a_2048 = Asset(url="https://example.com/assets/images/image-fc98b695.jpg?scale-down-to=2048&width=11760")
        a_canonical = Asset(url="https://example.com/assets/images/image-fc98b695.jpg")

        p_512 = downloader.prepare_local_path(a_512, self.path)
        p_1024 = downloader.prepare_local_path(a_1024, self.path)
        p_2048 = downloader.prepare_local_path(a_2048, self.path)
        p_canonical = downloader.prepare_local_path(a_canonical, self.path)

        self.assertIn("@512", p_512.name)
        self.assertIn("@1024", p_1024.name)
        self.assertIn("@2048", p_2048.name)
        self.assertEqual("image-fc98b695.jpg", p_canonical.name)

        # All four paths are completely distinct
        paths = {p_512, p_1024, p_2048, p_canonical}
        self.assertEqual(len(paths), 4)

    def test_binding_manifest_lookup_prevents_variant_overwriting(self):
        """ManifestLookup preserves canonical representation and exact variant matching."""
        manifest = [
            {
                "source": "https://example.com/assets/images/image-fc98b695.jpg?scale-down-to=512",
                "local": "/images/image-fc98b695@512.jpg",
                "category": "images",
                "size_bytes": 50000,
            },
            {
                "source": "https://example.com/assets/images/image-fc98b695.jpg?scale-down-to=1024",
                "local": "/images/image-fc98b695@1024.jpg",
                "category": "images",
                "size_bytes": 120000,
            },
            {
                "source": "https://example.com/assets/images/image-fc98b695.jpg?scale-down-to=2048",
                "local": "/images/image-fc98b695@2048.jpg",
                "category": "images",
                "size_bytes": 350000,
            },
        ]

        lookup = ManifestLookup(manifest)

        # 1. Exact query matches exact variant
        item_512 = lookup.get_match("https://example.com/assets/images/image-fc98b695.jpg?scale-down-to=512")
        self.assertEqual(item_512["local"], "/images/image-fc98b695@512.jpg")

        # 2. Clean URL matches highest resolution/canonical variant
        item_canonical = lookup.get_match("https://example.com/assets/images/image-fc98b695.jpg")
        self.assertEqual(item_canonical["local"], "/images/image-fc98b695@2048.jpg")

        # 3. Variants list returns all 3
        vars_list = lookup.get_variants("https://example.com/assets/images/image-fc98b695.jpg")
        self.assertEqual(len(vars_list), 3)

    def test_asset_binding_attaches_variants(self):
        """AssetBindingEngine attaches evidence-backed variants to bindings."""
        manifest = [
            {
                "source": "https://example.com/assets/images/image-fc98b695.jpg?scale-down-to=512",
                "local": "/images/image-fc98b695@512.jpg",
                "category": "images",
                "size_bytes": 50000,
            },
            {
                "source": "https://example.com/assets/images/image-fc98b695.jpg?scale-down-to=1024",
                "local": "/images/image-fc98b695@1024.jpg",
                "category": "images",
                "size_bytes": 120000,
            },
        ]

        dom = {
            "tag": "body",
            "children": [
                {
                    "tag": "img",
                    "src": "https://example.com/assets/images/image-fc98b695.jpg",
                    "classes": ["hero-image"],
                }
            ]
        }

        engine = AssetBindingEngine()
        bindings = engine.bind(dom, {}, manifest, [], [])
        self.assertEqual(len(bindings), 1)
        binding = bindings[0]
        self.assertEqual(len(binding.variants), 2)
        widths = [v["width"] for v in binding.variants]
        self.assertEqual(widths, [512, 1024])

    def test_static_generator_emits_srcset_when_variants_exist(self):
        """Static generator emits srcset when asset has genuine variants."""
        ir = {
            "metadata": {"title": "Srcset Test"},
            "routes": ["/"],
            "asset_bindings": [
                {
                    "asset_id": "hero-image-0",
                    "source_url": "https://example.com/assets/images/hero.jpg",
                    "local_path": "public/images/hero.jpg",
                    "role": "image",
                    "variants": [
                        {"local_path": "public/images/hero@512.jpg", "width": 512},
                        {"local_path": "public/images/hero@1024.jpg", "width": 1024},
                    ]
                }
            ],
            "pages": [
                {
                    "route": "/",
                    "title": "Home",
                    "dom": {
                        "tag": "img",
                        "attributes": {"src": "https://example.com/assets/images/hero.jpg"},
                    }
                }
            ]
        }

        gen = StaticProjectGenerator(ir, self.path / "static")
        gen.generate()

        html_file = self.path / "static" / "index.html"
        self.assertTrue(html_file.exists())
        html_content = html_file.read_text(encoding="utf-8")

        self.assertIn('srcset="assets/images/hero@512.jpg 512w, assets/images/hero@1024.jpg 1024w"', html_content)
        self.assertIn('sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"', html_content)


if __name__ == "__main__":
    unittest.main()
