from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from webextractor.assets.binding import AssetBindingEngine
from webextractor.generator.dom_emitter import DomToJsxEmitter
from webextractor.generator.project import ReactProjectGenerator


class TestPhase2AssetBinding(unittest.TestCase):
    def test_subpage_and_overlay_assets_traversal(self):
        """Proves AssetBindingEngine traverses DOM trees of subpages and overlay."""
        engine = AssetBindingEngine()
        subpage_dom = {
            "tag": "div",
            "children": [
                {
                    "tag": "img",
                    "src": "https://framerusercontent.com/images/subpage-img.png?w=800",
                }
            ],
        }
        overlay_dom = {
            "tag": "div",
            "id": "overlay",
            "styles": {
                "backgroundImage": 'url("https://framerusercontent.com/images/pattern.svg?w=128")'
            },
            "children": [],
        }
        manifest = [
            {
                "source": "https://framerusercontent.com/images/subpage-img.png",
                "local": "/images/subpage-img.png",
                "downloaded": True,
                "category": "images",
            },
            {
                "source": "https://framerusercontent.com/images/pattern.svg",
                "local": "/icons/pattern.svg",
                "downloaded": True,
                "category": "icons",
            },
        ]

        bindings = engine.bind(
            rendered_dom=None,
            viewports={},
            asset_manifest=manifest,
            page_components=[],
            reusable_components=[],
            pages=[{"route": "/work/agriai", "dom": subpage_dom}],
            overlay=overlay_dom,
        )

        bound_urls = [b.source_url for b in bindings]
        self.assertTrue(any("subpage-img.png" in u for u in bound_urls))
        self.assertTrue(any("pattern.svg" in u for u in bound_urls))

    def test_query_string_variants_and_local_vs_remote_resolution(self):
        """Proves DomToJsxEmitter resolves query-string variants to downloaded local paths and never emits remote URL."""
        assets = [
            {
                "source": "https://framerusercontent.com/images/photo.png",
                "local": "/images/photo.png",
                "downloaded": True,
                "category": "image",
            },
            {
                "source": "https://framerusercontent.com/images/pattern.svg",
                "local": "/icons/pattern.svg",
                "downloaded": True,
                "category": "icon",
            },
        ]
        emitter = DomToJsxEmitter(assets=assets)

        # 1. Image with query-string variant should resolve to local path
        node = {
            "tag": "img",
            "src": "https://framerusercontent.com/images/photo.png?scale-down-to=1024&w=1200",
            "attributes": {},
        }
        resolved = emitter._resolve_image_src(node)
        self.assertEqual(resolved, "/images/photo.png")
        self.assertNotIn("https://framerusercontent.com", resolved)

        # 2. SVG in style url(...) should resolve to local path
        style_str = "background-image: url('https://framerusercontent.com/images/pattern.svg?width=128&height=128')"
        parsed_style = emitter._parse_style_attribute(style_str)
        self.assertIn("/icons/pattern.svg", parsed_style)
        self.assertNotIn("framerusercontent.com", parsed_style)

        # 3. Unresolved remote asset not in manifest is allowed as remote fallback
        node_external = {
            "tag": "img",
            "src": "https://external-cdn.com/unknown.png",
            "attributes": {},
        }
        resolved_ext = emitter._resolve_image_src(node_external)
        self.assertEqual(resolved_ext, "https://external-cdn.com/unknown.png")

    def test_asset_verification_invariant_check(self):
        """Proves ProjectGenerator verifies local asset existence and detects missing local files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir)
            pub_img = out_path / "public/images"
            pub_img.mkdir(parents=True)
            # Create real file for photo.png
            (pub_img / "photo.png").write_text("fake image content")

            site_ir = {
                "metadata": {"title": "Invariant Check Test"},
                "routes": ["/"],
                "components": {
                    "tag": "div",
                    "children": [
                        {
                            "tag": "section",
                            "attributes": {"data-component-name": "Hero"},
                            "children": [
                                {"tag": "img", "src": "/images/photo.png"},
                                {"tag": "img", "src": "/images/missing-file.png"},
                            ],
                        }
                    ],
                },
                "pages": [
                    {
                        "route": "/",
                        "components": ["Hero"],
                    }
                ],
                "design_system": {},
            }

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            report_path = out_path / "analysis/asset_verification.json"
            self.assertTrue(report_path.exists())
            import json
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("/images/photo.png", report["resolved_local_assets"])
            self.assertIn("/images/missing-file.png", report["unresolved_assets"])
            self.assertEqual(report["status"], "FAIL")
