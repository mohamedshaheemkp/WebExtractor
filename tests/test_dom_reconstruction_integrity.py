from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.analysis.source_css import extract_relevant_css
from webextractor.generator.dom_emitter import DomToJsxEmitter
from webextractor.generator.project import ReactProjectGenerator
from webextractor.model.site_ir import SiteIR


class TestDomReconstructionIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_structural_partitioning_disjoint_conservation(self):
        """Validates that decomposing a rendered DOM into sections conserves all nodes with 0 duplicate ancestors."""
        # Synthesize a multi-level page with wrapper and 3 child sections
        tree = {
            "tag": "div",
            "id": "root",
            "classes": ["site-container", "layout-root"],
            "attributes": {"style": "min-height: 100vh; display: flex; flex-direction: column;"},
            "children": [
                {
                    "tag": "header",
                    "classes": ["nav-bar"],
                    "children": [
                        {"tag": "a", "attributes": {"href": "/"}, "text": "Logo", "children": []},
                        {"tag": "nav", "children": [{"tag": "a", "attributes": {"href": "/work"}, "text": "Work", "children": []}]},
                    ],
                },
                {
                    "tag": "section",
                    "id": "hero",
                    "classes": ["hero-section"],
                    "attributes": {"data-component-name": "Hero"},
                    "children": [
                        {"tag": "h1", "text": "Headline", "children": []},
                        {"tag": "p", "text": "Subhead", "children": []},
                    ],
                },
                {
                    "tag": "footer",
                    "classes": ["site-footer"],
                    "children": [
                        {"tag": "p", "text": "Copyright 2026", "children": []},
                    ],
                },
            ],
        }

        content_root, sections = DomToJsxEmitter.decompose_content_sections(tree)
        self.assertIsNotNone(content_root)
        self.assertEqual(content_root.get("id"), "root")
        self.assertEqual(len(sections), 3)

        def count_nodes(n):
            return 1 + sum(count_nodes(c) for c in n.get("children", []) if isinstance(c, dict))

        root_nodes = count_nodes(content_root)
        section_nodes = sum(sec["nodes_count"] for sec in sections)
        # Invariant: 1 content root + direct section nodes == total root nodes
        self.assertEqual(root_nodes, section_nodes + 1)

        # Verify section names are unique and match structure
        names = [s["name"] for s in sections]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names[0], "HeaderNavigation")
        self.assertEqual(names[1], "Hero")
        self.assertEqual(names[2], "Footer")

    def test_no_full_page_ancestor_as_child_section(self):
        """Validates that find_node_for_component strictly rejects an ancestor container containing multiple sections."""
        tree = {
            "tag": "div",
            "classes": ["page-wrapper"],
            "children": [
                {
                    "tag": "header",
                    "id": "header",
                    "text": "Header contact us",
                    "children": [],
                },
                {
                    "tag": "section",
                    "id": "hero",
                    "text": "Hero banner",
                    "children": [],
                },
                {
                    "tag": "section",
                    "id": "contact",
                    "text": "Get in touch with us today",
                    "children": [],
                },
            ],
        }

        emitter = DomToJsxEmitter(tree)

        # "CTA" or "Contact" must match section#contact, NEVER div.page-wrapper
        cta_node = emitter.find_node_for_component("CTA")
        self.assertIsNotNone(cta_node)
        self.assertEqual(cta_node.get("id"), "contact")
        self.assertEqual(cta_node.get("tag"), "section")

        # "Hero" must match section#hero, NEVER div.page-wrapper
        hero_node = emitter.find_node_for_component("Hero")
        self.assertIsNotNone(hero_node)
        self.assertEqual(hero_node.get("id"), "hero")

    def test_layout_wrapper_preservation_in_home_page(self):
        """Validates that app/page.tsx preserves the content root wrapper element and its classes/styles."""
        site_ir = {
            "metadata": {"title": "Wrapper Test Site"},
            "routes": ["/"],
            "design_system": {},
            "pages": [
                {
                    "route": "/",
                    "components": [
                        {"name": "HeaderNavigation", "type": "header"},
                        {"name": "Hero", "type": "section"},
                        {"name": "Footer", "type": "footer"},
                    ],
                }
            ],
            "components": {
                "tag": "div",
                "classes": ["framer-vGE5i", "outer-layout"],
                "attributes": {"style": "min-height: 100vh; width: auto;"},
                "children": [
                    {"tag": "header", "id": "nav", "children": []},
                    {"tag": "section", "id": "hero", "children": []},
                    {"tag": "footer", "id": "foot", "children": []},
                ],
            },
        }

        generator = ReactProjectGenerator(site_ir, self.temp_dir)
        generator.generate()

        page_tsx = (self.temp_dir / "app/page.tsx").read_text(encoding="utf-8")
        # Wrapper element must be present around page sections
        self.assertIn('className="framer-vGE5i outer-layout"', page_tsx)
        self.assertIn("minHeight", page_tsx)
        self.assertIn("<HeaderNavigation />", page_tsx)
        self.assertIn("<Hero />", page_tsx)
        self.assertIn("<Footer />", page_tsx)

    def test_image_src_and_srcset_fallback(self):
        """Validates that _resolve_image_src extracts from srcset if src is absent and keeps authentic URLs."""
        emitter = DomToJsxEmitter(
            asset_bindings=[
                {"role": "image", "source_url": "https://example.com/pic.png", "local_path": "/assets/pic.png"}
            ]
        )

        # 1. Image with matching binding
        node_with_src = {"tag": "img", "attributes": {"src": "https://example.com/pic.png"}}
        self.assertEqual(emitter._resolve_image_src(node_with_src), "/assets/pic.png")

        # 2. Image with only srcset and no src
        node_with_srcset = {
            "tag": "img",
            "attributes": {"srcset": "https://cdn.example.com/large.jpg 1200w, https://cdn.example.com/small.jpg 600w"},
        }
        self.assertEqual(emitter._resolve_image_src(node_with_srcset), "https://cdn.example.com/large.jpg")

        # 3. Image with authentic absolute URL not in bindings
        node_unbound = {"tag": "img", "attributes": {"src": "https://images.unsplash.com/photo-12345"}}
        self.assertEqual(emitter._resolve_image_src(node_unbound), "https://images.unsplash.com/photo-12345")

    def test_responsive_breakpoint_display_rules_generation(self):
        """Validates that source_css extracts responsive media display rules from HTML breakpoint metadata."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
          <script id="__framer__breakpoints" type="application/json">
            [
              {"hash": "13l4a8r", "media": "(max-width: 809.98px)"},
              {"hash": "7rggy9", "media": "(min-width: 1440px)"}
            ]
          </script>
        </head>
        <body>
          <div class="hidden-13l4a8r">Desktop Only</div>
          <div class="hidden-7rggy9">Mobile Only</div>
        </body>
        </html>
        """
        result = extract_relevant_css(
            html_content=html,
            referenced_classes={"hidden-13l4a8r", "hidden-7rggy9"},
        )
        media_rules = result.get("media_rules", [])
        self.assertTrue(any("hidden-13l4a8r" in r and "display: none !important" in r for r in media_rules))
        self.assertTrue(any("hidden-7rggy9" in r and "display: none !important" in r for r in media_rules))

    def test_work_index_page_generation(self):
        """Validates that app/work/page.tsx is generated as a collection index to prevent 404s."""
        site_ir = {
            "metadata": {"title": "Portfolio"},
            "routes": ["/", "/work/project-one"],
            "design_system": {},
            "data": {
                "projects": [
                    {"slug": "project-one", "title": "Project One", "description": "Case study one", "category": "AI"}
                ]
            },
            "pages": [{"route": "/", "components": []}],
        }
        generator = ReactProjectGenerator(site_ir, self.temp_dir)
        generator.generate()

        work_index_path = self.temp_dir / "app/work/page.tsx"
        self.assertTrue(work_index_path.exists())
        content = work_index_path.read_text(encoding="utf-8")
        self.assertIn("Selected Work", content)
        self.assertIn("/work/project-one", content)


if __name__ == "__main__":
    unittest.main()
