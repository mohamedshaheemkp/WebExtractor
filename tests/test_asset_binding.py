import json
import tempfile
import unittest
from pathlib import Path

from webextractor.assets.binding import AssetBinding, AssetBindingEngine
from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.generator.project import ReactProjectGenerator
from webextractor.model.site_ir import SiteIR


class TestAssetBindingEngine(unittest.TestCase):

    def setUp(self):
        self.binding_engine = AssetBindingEngine()

        self.mock_manifest = [
            {
                "source": "https://origins.example.com/assets/hero-bg.webp",
                "local": "/images/hero-bg.webp",
                "format": "webp",
                "size_bytes": 104200,
                "category": "images",
            },
            {
                "source": "https://origins.example.com/assets/hero-reel.mp4",
                "local": "/videos/hero-reel.mp4",
                "format": "mp4",
                "size_bytes": 1250000,
                "category": "videos",
            },
            {
                "source": "https://origins.example.com/assets/hero-poster.webp",
                "local": "/images/hero-poster.webp",
                "format": "webp",
                "size_bytes": 45000,
                "category": "images",
            },
            {
                "source": "https://origins.example.com/assets/project-alpha.png",
                "local": "/images/project-alpha.png",
                "format": "png",
                "size_bytes": 82000,
                "category": "images",
            },
            {
                "source": "https://origins.example.com/assets/logo.svg",
                "local": "/images/logo.svg",
                "format": "svg",
                "size_bytes": 3500,
                "category": "images",
            },
        ]

        self.mock_dom = {
            "tag": "body",
            "children": [
                {
                    "tag": "header",
                    "classes": ["header-nav"],
                    "children": [
                        {"tag": "img", "src": "https://origins.example.com/assets/logo.svg", "classes": ["logo"]}
                    ]
                },
                {
                    "tag": "section",
                    "id": "hero",
                    "classes": ["hero-section"],
                    "children": [
                        {
                            "tag": "video",
                            "src": "https://origins.example.com/assets/hero-reel.mp4",
                            "poster": "https://origins.example.com/assets/hero-poster.webp",
                        }
                    ]
                },
                {
                    "tag": "section",
                    "id": "projects",
                    "classes": ["projects-grid"],
                    "children": [
                        {
                            "tag": "article",
                            "classes": ["project-card"],
                            "children": [
                                {"tag": "img", "src": "https://origins.example.com/assets/project-alpha.png", "classes": ["preview"]}
                            ]
                        }
                    ]
                }
            ]
        }

    # 1. Asset Binding Generation
    def test_asset_binding_generation(self):
        bindings = self.binding_engine.bind(
            rendered_dom=self.mock_dom,
            viewports={"desktop": {"dom": self.mock_dom}},
            asset_manifest=self.mock_manifest,
            page_components=[{"name": "HeaderNavigation"}, {"name": "Hero"}, {"name": "Projects"}],
            reusable_components=[{"name": "ProjectCard"}],
        )

        self.assertTrue(len(bindings) >= 4)
        roles = {b.role for b in bindings}
        self.assertIn("logo", roles)
        self.assertIn("video", roles)
        self.assertIn("poster", roles)
        self.assertIn("image", roles)

    # 2. Component -> Asset Relationship
    def test_component_asset_relationship(self):
        bindings = self.binding_engine.bind(
            rendered_dom=self.mock_dom,
            viewports={"desktop": {"dom": self.mock_dom}},
            asset_manifest=self.mock_manifest,
            page_components=[{"name": "HeaderNavigation"}, {"name": "Hero"}, {"name": "Projects"}],
            reusable_components=[{"name": "ProjectCard"}],
        )

        comp_roles = {(b.component, b.role) for b in bindings}
        self.assertIn(("HeaderNavigation", "logo"), comp_roles)
        self.assertIn(("Hero", "video"), comp_roles)
        self.assertIn(("Hero", "poster"), comp_roles)
        self.assertIn(("ProjectCard", "image"), comp_roles)

    # 3. Local Generated Asset Paths
    def test_local_generated_asset_paths(self):
        bindings = self.binding_engine.bind(
            rendered_dom=self.mock_dom,
            viewports={"desktop": {"dom": self.mock_dom}},
            asset_manifest=self.mock_manifest,
            page_components=[{"name": "HeaderNavigation"}, {"name": "Hero"}, {"name": "Projects"}],
            reusable_components=[{"name": "ProjectCard"}],
        )

        for b in bindings:
            if b.resolved:
                self.assertTrue(b.local_path.startswith(("/images/", "/videos/", "/fonts/")))

        logo_binding = next(b for b in bindings if b.component == "HeaderNavigation" and b.role == "logo")
        self.assertEqual(logo_binding.local_path, "/images/logo.svg")

        video_binding = next(b for b in bindings if b.component == "Hero" and b.role == "video")
        self.assertEqual(video_binding.local_path, "/videos/hero-reel.mp4")

    # 4. Missing / Unresolved Assets Graceful Handling
    def test_missing_unresolved_assets(self):
        # DOM references an asset not in the downloaded manifest
        unresolved_dom = {
            "tag": "body",
            "children": [
                {
                    "tag": "section",
                    "id": "hero",
                    "children": [
                        {"tag": "img", "src": "https://unreachable.cdn.com/missing-404.webp"}
                    ]
                }
            ]
        }

        bindings = self.binding_engine.bind(
            rendered_dom=unresolved_dom,
            viewports={"desktop": {"dom": unresolved_dom}},
            asset_manifest=self.mock_manifest,  # does not contain missing-404.webp
            page_components=[{"name": "Hero"}],
            reusable_components=[],
        )

        # Should not crash, and mark resolved=False with empty local_path
        unresolved_b = next((b for b in bindings if "missing-404" in b.source_url), None)
        self.assertIsNotNone(unresolved_b)
        self.assertFalse(unresolved_b.resolved)
        self.assertEqual(unresolved_b.local_path, "")

    # 5. Deterministic Output
    def test_deterministic_output(self):
        bindings_1 = self.binding_engine.bind(
            rendered_dom=self.mock_dom,
            viewports={"desktop": {"dom": self.mock_dom}},
            asset_manifest=self.mock_manifest,
            page_components=[{"name": "HeaderNavigation"}, {"name": "Hero"}, {"name": "Projects"}],
            reusable_components=[{"name": "ProjectCard"}],
        )

        bindings_2 = self.binding_engine.bind(
            rendered_dom=self.mock_dom,
            viewports={"desktop": {"dom": self.mock_dom}},
            asset_manifest=self.mock_manifest,
            page_components=[{"name": "HeaderNavigation"}, {"name": "Hero"}, {"name": "Projects"}],
            reusable_components=[{"name": "ProjectCard"}],
        )

        dict_1 = [b.to_dict() for b in bindings_1]
        dict_2 = [b.to_dict() for b in bindings_2]

        self.assertEqual(json.dumps(dict_1, sort_keys=True), json.dumps(dict_2, sort_keys=True))

    # 6. Generator Consumption & Regression
    def test_generator_consumes_asset_bindings(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)

            site_ir = SiteIR(
                metadata={"title": "Origins System", "url": "https://origins.example.com"},
                routes=["/"],
                design_system={},
                pages=[{"route": "/", "components": ["HeaderNavigation", "Hero", "Projects"]}],
                reusable_components=[{"name": "ProjectCard"}],
                asset_bindings=[
                    {
                        "asset_id": "hero-vid-1",
                        "source_url": "https://origins.example.com/reel.mp4",
                        "local_path": "/videos/reel.mp4",
                        "type": "video",
                        "role": "video",
                        "component": "Hero",
                    },
                    {
                        "asset_id": "header-logo-1",
                        "source_url": "https://origins.example.com/logo.svg",
                        "local_path": "/images/logo.svg",
                        "type": "image",
                        "role": "logo",
                        "component": "HeaderNavigation",
                    }
                ],
                data={
                    "projects": [
                        {
                            "title": "Origins Core",
                            "description": "Next-generation generative web engine.",
                            "image": "/images/origins-core.png",
                            "tags": ["React", "Next.js"],
                        }
                    ]
                }
            )

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            # Verify HeaderNavigation renders the bound logo
            header_code = (out_path / "components/HeaderNavigation.tsx").read_text(encoding="utf-8")
            self.assertIn('/images/logo.svg', header_code)

            # Verify Hero renders the bound video
            hero_code = (out_path / "components/Hero.tsx").read_text(encoding="utf-8")
            self.assertIn('<video', hero_code)
            self.assertIn('/videos/reel.mp4', hero_code)

            # Verify ProjectCard renders project.image
            card_code = (out_path / "components/ProjectCard.tsx").read_text(encoding="utf-8")
            self.assertIn('src={project.image}', card_code)

            # Verify asset_bindings.json was written
            self.assertTrue((out_path / "analysis/asset_bindings.json").exists())


if __name__ == "__main__":
    unittest.main()
