import json
import tempfile
import unittest
from pathlib import Path

from webextractor.generator.project import ReactProjectGenerator
from webextractor.model.site_ir import SiteIR
from webextractor.analysis.analyzer import SiteAnalyzer


class TestReactProjectGenerator(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.test_dir.name)

        self.sample_ir = {
            "metadata": {
                "title": "Mohamed Shaheem — Principal Engineer",
                "url": "https://origins.example.com",
            },
            "routes": ["/", "/contact", "/work/webextractor"],
            "design_system": {
                "colors": {
                    "background": "#0a0a0a",
                    "foreground": "#ffffff",
                    "primary": "#3b82f6",
                },
                "typography": {
                    "sizes": {
                        "h1": "4rem",
                        "body": "1rem",
                    },
                    "display": {"family": "Inter, sans-serif"},
                    "body": {"family": "Inter, sans-serif"},
                },
                "radii": {
                    "card": "16px",
                    "pill": "9999px",
                },
            },
            "responsive_rules": [],
            "pages": [
                {
                    "route": "/",
                    "components": [
                        "HeaderNavigation",
                        "Hero",
                        "Intro",
                        "Projects",
                        "About",
                        "Capabilities",
                        "VoiceOfMS",
                        "Journey",
                        "Toolkit",
                        "CTA",
                        "Footer",
                    ],
                }
            ],
            "reusable_components": [
                {"name": "ProjectCard", "instances": 5},
                {"name": "CapabilityItem", "instances": 4},
                {"name": "JourneyItem", "instances": 6},
                {"name": "ToolkitItem", "instances": 12},
                {"name": "NavItem", "instances": 6},
            ],
            "component_styles": {
                "Hero": {
                    "desktop": {
                        "display": "flex",
                        "minHeight": "100vh",
                        "padding": "80px",
                    },
                    "mobile": {
                        "display": "block",
                        "padding": "24px",
                    },
                },
                "Projects": {
                    "desktop": {"padding": "100px 64px"},
                    "mobile": {"padding": "40px 20px"},
                },
            },
            "data": {
                "projects": [
                    {
                        "title": "WebExtractor Engine",
                        "description": "High-fidelity reverse engineering pipeline.",
                        "tags": ["Python", "Playwright", "Next.js"],
                    }
                ],
                "capabilities": [
                    {
                        "title": "Interface Architecture",
                        "description": "Scalable design systems.",
                    }
                ],
            },
        }

    def tearDown(self):
        self.test_dir.cleanup()

    def test_react_project_generation(self):
        generator = ReactProjectGenerator(self.sample_ir, self.output_dir)
        res_dir = generator.generate()

        self.assertEqual(res_dir, self.output_dir)

        # Check directory structure
        self.assertTrue((self.output_dir / "app").is_dir())
        self.assertTrue((self.output_dir / "components").is_dir())
        self.assertTrue((self.output_dir / "data").is_dir())
        self.assertTrue((self.output_dir / "styles").is_dir())
        self.assertTrue((self.output_dir / "analysis").is_dir())
        self.assertTrue((self.output_dir / "public/images").is_dir())

        # Check core App Router files
        self.assertTrue((self.output_dir / "app/layout.tsx").exists())
        self.assertTrue((self.output_dir / "app/page.tsx").exists())
        self.assertTrue((self.output_dir / "app/globals.css").exists())
        self.assertTrue((self.output_dir / "app/contact/page.tsx").exists())
        self.assertTrue((self.output_dir / "app/work/[slug]/page.tsx").exists())

        # Check components
        self.assertTrue((self.output_dir / "components/HeaderNavigation.tsx").exists())
        self.assertTrue((self.output_dir / "components/Hero.tsx").exists())
        self.assertTrue((self.output_dir / "components/Projects.tsx").exists())
        self.assertTrue((self.output_dir / "components/ProjectCard.tsx").exists())
        self.assertTrue((self.output_dir / "components/Capabilities.tsx").exists())
        self.assertTrue((self.output_dir / "components/CapabilityItem.tsx").exists())
        self.assertTrue((self.output_dir / "components/Journey.tsx").exists())
        self.assertTrue((self.output_dir / "components/JourneyItem.tsx").exists())
        self.assertTrue((self.output_dir / "components/Toolkit.tsx").exists())
        self.assertTrue((self.output_dir / "components/ToolkitItem.tsx").exists())
        self.assertTrue((self.output_dir / "components/CTA.tsx").exists())
        self.assertTrue((self.output_dir / "components/Footer.tsx").exists())

        # Check data
        self.assertTrue((self.output_dir / "data/projects.ts").exists())
        self.assertTrue((self.output_dir / "data/capabilities.ts").exists())
        self.assertTrue((self.output_dir / "data/journey.ts").exists())
        self.assertTrue((self.output_dir / "data/toolkit.ts").exists())

        # Check tokens & analysis
        self.assertTrue((self.output_dir / "styles/tokens.css").exists())
        self.assertTrue((self.output_dir / "analysis/source-ir.json").exists())
        self.assertTrue((self.output_dir / "package.json").exists())
        self.assertTrue((self.output_dir / "tsconfig.json").exists())
        self.assertTrue((self.output_dir / "next.config.ts").exists())

        # Check layout content
        layout_text = (self.output_dir / "app/layout.tsx").read_text(encoding="utf-8")
        self.assertIn("Mohamed Shaheem", layout_text)
        self.assertIn('import "../styles/tokens.css";', layout_text)
        self.assertIn('import "./globals.css";', layout_text)

        # Check page content
        page_text = (self.output_dir / "app/page.tsx").read_text(encoding="utf-8")
        self.assertIn("import HeaderNavigation", page_text)
        self.assertIn("import Hero", page_text)
        self.assertIn("import Projects", page_text)
        self.assertIn("<Projects />", page_text)

        # Check tokens CSS
        tokens_text = (self.output_dir / "styles/tokens.css").read_text(encoding="utf-8")
        self.assertIn("--color-background: #0a0a0a;", tokens_text)
        self.assertIn("--color-primary: #3b82f6;", tokens_text)
        self.assertIn("--font-display: Inter, sans-serif;", tokens_text)

        # Check globals CSS with responsive classes
        globals_text = (self.output_dir / "app/globals.css").read_text(encoding="utf-8")
        self.assertIn(".hero {", globals_text)
        self.assertIn("@media (max-width: 768px)", globals_text)

    def test_site_analyzer_to_site_ir(self):
        analyzer = SiteAnalyzer()
        mock_capture = {
            "url": "https://example.com",
            "html": "<html><head><title>Test Site</title></head><body><header>Nav</header><section id='hero'><h1>Hello</h1></section><section id='projects'><h2>Projects</h2><div>Project 1</div><div>Project 2</div></section><footer>Foot</footer></body></html>",
            "dom": {
                "tag": "body",
                "children": [
                    {"tag": "header", "classes": ["nav"], "text": "Nav", "children": []},
                    {"tag": "section", "id": "hero", "classes": ["hero-section"], "text": "Hello", "children": []},
                    {"tag": "section", "id": "projects", "classes": ["projects-grid"], "text": "Projects", "children": [
                        {"tag": "div", "classes": ["project-card"], "text": "Alpha Project", "children": []},
                        {"tag": "div", "classes": ["project-card"], "text": "Beta Project", "children": []},
                    ]},
                    {"tag": "footer", "classes": ["footer"], "text": "Foot", "children": []},
                ]
            },
            "requests": [],
        }

        site_model = analyzer.analyze(mock_capture)
        self.assertTrue(hasattr(site_model, "pages"))
        self.assertTrue(hasattr(site_model, "reusable_components"))
        self.assertTrue(hasattr(site_model, "component_styles"))
        self.assertTrue(hasattr(site_model, "data"))

        # Verify SiteIR
        site_ir = SiteIR(
            metadata={"title": site_model.title, "url": site_model.url},
            routes=site_model.routes,
            design_system=getattr(site_model, "design_system", {}),
            pages=getattr(site_model, "pages", []),
            reusable_components=getattr(site_model, "reusable_components", []),
            component_styles=getattr(site_model, "component_styles", {}),
            data=getattr(site_model, "data", {}),
        )

        site_ir.save(self.output_dir / "analysis")
        self.assertTrue((self.output_dir / "analysis/source-ir.json").exists())
        self.assertTrue((self.output_dir / "analysis/site_ir.json").exists())

    def test_regression_no_fabricated_portfolio_copy(self):
        """Regression test: fabricated copy must NEVER be emitted by generator."""
        generator = ReactProjectGenerator(
            site_ir={
                "metadata": {"title": "Test Portfolio"},
                "pages": [{"name": "Home", "components": ["HeaderNavigation", "Hero", "Intro", "Projects"]}],
                "data": {},
            },
            output_dir=self.output_dir,
        )
        generator.generate()

        hero_text = (self.output_dir / "components/Hero.tsx").read_text(encoding="utf-8")
        header_text = (self.output_dir / "components/HeaderNavigation.tsx").read_text(encoding="utf-8")
        projects_data = (self.output_dir / "data/projects.ts").read_text(encoding="utf-8")

        # 1. Fabricated hero copy must not appear
        self.assertNotIn("Portfolio • Engineering • Systems", hero_text)
        self.assertNotIn("Designing resilient, ultra-fast interfaces", hero_text)

        # 2. Fabricated brand logo must not appear
        self.assertNotIn("ORIGINS", header_text)

        # 3. Fabricated fallback projects must not appear
        self.assertNotIn("WebExtractor Engine", projects_data)
        self.assertNotIn("Origins System Studio", projects_data)

    def test_source_derived_content_generation(self):
        """Test that source-derived DOM content from SiteIR is faithfully emitted."""
        site_ir = {
            "metadata": {"title": "MHD SHM KP"},
            "pages": [{"name": "Home", "components": ["HeaderNavigation", "Hero", "Intro", "Projects"]}],
            "components": {
                "tag": "body",
                "text": "All Page Content",
                "children": [
                    {
                        "tag": "header",
                        "classes": ["nav-header"],
                        "text": "LOCAL/ 14:09:06 CONTACT NOW",
                        "children": [
                            {"tag": "a", "classes": ["btn-contact"], "text": "CONTACT NOW", "children": []}
                        ],
                    },
                    {
                        "tag": "section",
                        "classes": ["hero-sec"],
                        "text": "MHD SHM KP BASED IN INDIA, KERALA AVAILABLE ALL AROUND WORLDWIDE AI ENGINEER & DEV GRAPHIC DESIGNER",
                        "children": [
                            {"tag": "h1", "classes": ["title"], "text": "MHD SHM KP", "children": []},
                            {"tag": "p", "classes": ["role-1"], "text": "AI ENGINEER & DEV", "children": []},
                            {"tag": "p", "classes": ["role-2"], "text": "GRAPHIC DESIGNER", "children": []},
                        ],
                    },
                    {
                        "tag": "section",
                        "classes": ["intro-sec"],
                        "text": "01 // INTRO TOOLS&FRAMEWORKS I'M MOHAMED SHAHEEM KP",
                        "children": [
                            {"tag": "h2", "classes": ["eyebrow"], "text": "01 // INTRO", "children": []},
                        ],
                    },
                    {
                        "tag": "section",
                        "classes": ["projects-sec"],
                        "text": "02 //PROJECTS SELECTED PROJECTS AgriAi AI / MACHINE LEARNING Smart Folder Organiser MS Portfolio",
                        "children": [
                            {"tag": "h2", "classes": ["heading"], "text": "02 //PROJECTS", "children": []},
                            {
                                "tag": "div",
                                "classes": ["card-1"],
                                "text": "AgriAi AI / MACHINE LEARNING",
                                "children": [
                                    {"tag": "h3", "classes": ["card-title"], "text": "AgriAi", "children": []},
                                    {"tag": "p", "classes": ["card-cat"], "text": "AI / MACHINE LEARNING", "children": []},
                                ],
                            },
                        ],
                    },
                ],
            },
            "asset_bindings": [
                {
                    "component": "Hero",
                    "role": "image",
                    "local_path": "/images/hero-portrait.webp",
                }
            ],
            "data": {},
        }

        generator = ReactProjectGenerator(site_ir, self.output_dir)
        generator.generate()

        hero_text = (self.output_dir / "components/Hero.tsx").read_text(encoding="utf-8")
        self.assertIn("MHD SHM KP", hero_text)
        self.assertIn("AI ENGINEER & DEV", hero_text)
        self.assertIn("GRAPHIC DESIGNER", hero_text)

        intro_text = (self.output_dir / "components/Intro.tsx").read_text(encoding="utf-8")
        self.assertIn("01 // INTRO", intro_text)

        projects_text = (self.output_dir / "components/Projects.tsx").read_text(encoding="utf-8")
        self.assertIn("AgriAi", projects_text)

        header_text = (self.output_dir / "components/HeaderNavigation.tsx").read_text(encoding="utf-8")
        self.assertIn("CONTACT NOW", header_text)

    def test_missing_project_data_no_fabrication(self):
        """Test that empty project datasets do not result in synthetic projects."""
        generator = ReactProjectGenerator(
            site_ir={
                "metadata": {"title": "Empty Site"},
                "pages": [{"name": "Home", "components": ["Projects"]}],
                "data": {},
            },
            output_dir=self.output_dir,
        )
        generator.generate()

        projects_file = (self.output_dir / "data/projects.ts").read_text(encoding="utf-8")
        self.assertIn("export const projects: Project[] = [];", projects_file)

    def test_missing_asset_bindings_no_fake_paths(self):
        """Test that missing asset bindings do not create fake placeholder asset paths."""
        generator = ReactProjectGenerator(
            site_ir={
                "metadata": {"title": "No Assets Site"},
                "pages": [{"name": "Home", "components": ["Hero"]}],
                "components": {
                    "tag": "body",
                    "children": [
                        {
                            "tag": "section",
                            "classes": ["hero"],
                            "text": "Clean Hero",
                            "children": [{"tag": "img", "classes": ["avatar"], "children": []}],
                        }
                    ],
                },
                "asset_bindings": [],
            },
            output_dir=self.output_dir,
        )
        generator.generate()

        hero_code = (self.output_dir / "components/Hero.tsx").read_text(encoding="utf-8")
        self.assertNotIn("placeholder", hero_code.lower())
        self.assertNotIn("/images/project-placeholder", hero_code)


if __name__ == "__main__":
    unittest.main()

