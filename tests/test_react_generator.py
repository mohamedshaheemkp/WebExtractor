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

    def test_svg_viewbox_and_foreignobject_dimensions(self):
        """Test that SVG viewBox, foreignObject width/height, and inline styles are preserved in JSX."""
        generator = ReactProjectGenerator(
            site_ir={
                "metadata": {"title": "SVG Test Site"},
                "pages": [{"name": "Home", "components": ["Hero"]}],
                "components": {
                    "tag": "body",
                    "children": [
                        {
                            "tag": "section",
                            "classes": ["hero", "framer-1pf3p1p"],
                            "children": [
                                {
                                    "tag": "svg",
                                    "classes": ["framer-v9260z"],
                                    "attributes": {"viewBox": "0 0 2520 318"},
                                    "children": [
                                        {
                                            "tag": "foreignobject",
                                            "classes": ["framer-fit-text"],
                                            "attributes": {
                                                "width": "100%",
                                                "height": "100%",
                                                "transform": "scale(1)",
                                                "style": "overflow:visible;transform-origin:center center",
                                            },
                                            "children": [
                                                {
                                                    "tag": "h1",
                                                    "classes": ["framer-text"],
                                                    "text": "MHD SHM KP",
                                                    "attributes": {
                                                        "style": "--framer-font-size:397.38px; --framer-letter-spacing:-3px; --framer-line-height:80%",
                                                    },
                                                    "children": [],
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            },
            output_dir=self.output_dir,
        )
        generator.generate()

        hero_code = (self.output_dir / "components/Hero.tsx").read_text(encoding="utf-8")
        self.assertIn('viewBox="0 0 2520 318"', hero_code)
        self.assertIn('width="100%"', hero_code)
        self.assertIn('height="100%"', hero_code)
        self.assertIn('overflow: "visible"', hero_code)
        self.assertIn('"--framer-font-size": "397.38px"', hero_code)
        self.assertIn('"--framer-letter-spacing": "-3px"', hero_code)

    def test_foreignobject_defaults_to_100_percent(self):
        """Test that foreignObject without explicit width/height defaults to 100% to prevent 0x0 browser collapse."""
        from webextractor.generator.dom_emitter import DomToJsxEmitter
        emitter = DomToJsxEmitter()
        node = {
            "tag": "foreignobject",
            "classes": ["framer-fit-text"],
            "attributes": {},
            "children": [{"tag": "h1", "text": "Heading", "children": []}],
        }
        jsx = emitter.emit_jsx(node, depth=0)
        self.assertIn('width="100%"', jsx)
        self.assertIn('height="100%"', jsx)

    def test_source_css_and_preset_extraction(self):
        """Test that extract_relevant_css extracts referenced classes and presets without capturing unused classes."""
        from webextractor.analysis.source_css import extract_relevant_css
        sample_html = """
        <html>
        <head>
          <style>
            @font-face { font-family: "Clash Display"; src: url("clash.woff2"); }
            @font-face { font-family: "UnusedFont"; src: url("unused.woff2"); }
            .framer-1adz1xm { display: flex; flex-flow: row; padding: 0 110px; }
            .framer-styles-preset-vsc6z h3 { font-size: 90px; font-weight: 600; }
            .completely-unused-class { color: red; }
            @media (max-width: 768px) {
              .framer-1adz1xm { flex-direction: column; padding: 0 20px; }
              .unused-responsive { margin: 0; }
            }
          </style>
        </head>
        <body></body>
        </html>
        """
        referenced = {"framer-1adz1xm", "framer-styles-preset-vsc6z"}
        extracted = extract_relevant_css(sample_html, referenced, ["Clash Display"])

        # Font faces
        self.assertEqual(len(extracted["font_faces"]), 1)
        self.assertIn("Clash Display", extracted["font_faces"][0])
        self.assertNotIn("UnusedFont", extracted["font_faces"][0])

        # Class rules
        class_css = "\n".join(extracted["class_rules"])
        self.assertIn(".framer-1adz1xm", class_css)
        self.assertIn(".framer-styles-preset-vsc6z h3", class_css)
        self.assertNotIn(".completely-unused-class", class_css)

        # Media rules
        media_css = "\n".join(extracted["media_rules"])
        self.assertIn(".framer-1adz1xm", media_css)
        self.assertIn("flex-direction: column", media_css)
        self.assertNotIn(".unused-responsive", media_css)

    def test_globals_css_emits_extracted_rules(self):
        """Test that project generator emits extracted font-faces, element classes, and responsive rules to globals.css."""
        generator = ReactProjectGenerator(
            site_ir={
                "metadata": {"title": "CSS Test"},
                "pages": [{"name": "Home", "components": ["Hero"]}],
                "component_styles": {
                    "source_rules": {
                        "font_faces": ['@font-face { font-family: "Clash Display"; src: url("clash.woff2"); }'],
                        "class_rules": [".framer-styles-preset-vsc6z h3 {\n  font-size: 90px;\n}"],
                        "media_rules": ["@media (max-width: 768px) {\n  .framer-1adz1xm {\n    flex-direction: column;\n  }\n}"],
                    }
                },
            },
            output_dir=self.output_dir,
        )
        generator.generate()

        globals_css = (self.output_dir / "app/globals.css").read_text(encoding="utf-8")
        self.assertIn('@font-face { font-family: "Clash Display"', globals_css)
        self.assertIn(".framer-styles-preset-vsc6z h3 {", globals_css)
        self.assertIn("font-size: 90px;", globals_css)
        self.assertIn("@media (max-width: 768px)", globals_css)
        self.assertIn(".framer-1adz1xm", globals_css)

    def test_balanced_css_extraction_with_nested_at_rules(self):
        """Test that nested at-rules like @supports or @keyframes do not leave stray braces in subsequent selectors."""
        from webextractor.analysis.source_css import extract_relevant_css

        sample_html = """
        <html>
        <head>
          <style>
            p.framer-text[data-text-fill] { display: inline-block; }
            @supports (corner-shape:superellipse(2)) {
              :root { --one-if-corner-shape-supported: 1; }
            }
            .framer-cursor-none, .framer-cursor-none * {
              cursor: none !important;
            }
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
            .framer-spin { animation: spin 1s infinite; }
          </style>
        </head>
        <body></body>
        </html>
        """
        referenced = {"framer-cursor-none", "framer-spin"}
        extracted = extract_relevant_css(sample_html, referenced)

        class_rules = extracted["class_rules"]
        self.assertEqual(len(class_rules), 2)

        for rule in class_rules:
            # Rule must not have stray closing braces at start of selector
            self.assertFalse(rule.startswith("}"))
            self.assertFalse(rule.startswith("{"))
            # Braces inside rule must be strictly balanced
            self.assertEqual(rule.count("{"), rule.count("}"))

        # Verify specifically that framer-cursor-none selector is clean
        cursor_rule = next(r for r in class_rules if "framer-cursor-none" in r)
        self.assertTrue(cursor_rule.startswith(".framer-cursor-none"))
        self.assertNotIn("}.framer-cursor-none", cursor_rule)

        # Verify through full project generator
        generator = ReactProjectGenerator(
            site_ir={
                "metadata": {"title": "CSS Balance Test"},
                "pages": [{"name": "Home", "components": ["Hero"]}],
                "component_styles": {
                    "source_rules": extracted
                },
            },
            output_dir=self.output_dir,
        )
        generator.generate()

        globals_css = (self.output_dir / "app/globals.css").read_text(encoding="utf-8")
        self.assertEqual(globals_css.count("{"), globals_css.count("}"))
        self.assertNotIn("}.framer-cursor-none", globals_css)
        self.assertIn(".framer-cursor-none", globals_css)

    def test_animation_extraction_from_html_scripts(self):
        """Test that AnimationExtractor correctly extracts appear animations, spring physics, and cursor attributes."""
        from webextractor.analysis.animations import AnimationExtractor

        sample_html = """
        <html>
        <head>
          <script>
          {
            "v9260z": {
              "default": {
                "initial": { "opacity": 0.001, "y": -400 },
                "animate": {
                  "opacity": 1,
                  "y": 0,
                  "transition": { "damping": 40, "stiffness": 200, "delay": 0.2, "type": "spring" }
                }
              }
            }
          }
          </script>
        </head>
        <body data-framer-cursor="custom-cursor">
          <div data-framer-appear-id="v9260z">Title</div>
        </body>
        </html>
        """
        extracted = AnimationExtractor.extract_animations(sample_html)
        self.assertIn("v9260z", extracted["appear_animations"])
        anim = extracted["appear_animations"]["v9260z"]
        self.assertEqual(anim["initial"]["y"], -400)
        self.assertEqual(anim["animate"]["y"], 0)
        self.assertEqual(anim["transition"]["stiffness"], 200)
        self.assertTrue(extracted["has_cursor"])

    def test_video_sources_and_poster_extraction(self):
        """Test that AssetAnalyzer extracts video sources and poster images."""
        from webextractor.analysis.assets import AssetAnalyzer

        sample_html = """
        <html>
        <body>
          <video poster="https://example.com/poster.jpg">
            <source src="https://example.com/video.mp4" type="video/mp4">
            <source src="https://example.com/video.webm" type="video/webm">
          </video>
        </body>
        </html>
        """
        analyzer = AssetAnalyzer()
        extracted = analyzer.analyze(sample_html, base_url="https://example.com")
        self.assertIn("https://example.com/video.mp4", extracted["videos"])
        self.assertIn("https://example.com/video.webm", extracted["videos"])
        self.assertIn("https://example.com/poster.jpg", extracted["images"])

    def test_multi_page_route_generation(self):
        """Test that project generator writes real pages for all discovered routes."""
        generator = ReactProjectGenerator(
            site_ir={
                "metadata": {"title": "Multi Route Site"},
                "routes": ["/", "/contact", "/work/agriai", "/work/ms-portfolio"],
                "pages": [{"name": "Home", "components": ["Hero"]}],
                "data": {
                    "projects": [
                        {
                            "slug": "agriai",
                            "title": "AgriAi",
                            "category": "AI / Machine Learning",
                            "description": "Smart farming interface.",
                        },
                        {
                            "slug": "ms-portfolio",
                            "title": "MS Portfolio",
                            "category": "Creative Development",
                            "description": "Personal creative portfolio.",
                        }
                    ]
                },
            },
            output_dir=self.output_dir,
        )
        generator.generate()

        self.assertTrue((self.output_dir / "app/page.tsx").exists())
        self.assertTrue((self.output_dir / "app/contact/page.tsx").exists())
        self.assertTrue((self.output_dir / "app/work/agriai/page.tsx").exists())
        self.assertTrue((self.output_dir / "app/work/ms-portfolio/page.tsx").exists())
        self.assertTrue((self.output_dir / "app/work/[slug]/page.tsx").exists())

        agriai_page = (self.output_dir / "app/work/agriai/page.tsx").read_text(encoding="utf-8")
        self.assertIn("AgriAi", agriai_page)
        self.assertIn("AI / Machine Learning", agriai_page)

    def test_layout_runtime_components_and_motion(self):
        """Test that layout.tsx includes FramerAppearRuntime with extracted animations."""
        generator = ReactProjectGenerator(
            site_ir={
                "metadata": {"title": "Motion Site"},
                "pages": [{"name": "Home", "components": ["Hero"]}],
                "animations": {
                    "appear_animations": {
                        "v9260z": {
                            "initial": {"opacity": 0.001, "y": -400},
                            "animate": {"opacity": 1, "y": 0},
                        }
                    },
                    "has_cursor": True,
                },
            },
            output_dir=self.output_dir,
        )
        generator.generate()

        layout_code = (self.output_dir / "app/layout.tsx").read_text(encoding="utf-8")
        self.assertIn("FramerAppearRuntime", layout_code)
        self.assertIn("CursorFollower", layout_code)
        self.assertIn("v9260z", layout_code)

        self.assertTrue((self.output_dir / "components/FramerAppearRuntime.tsx").exists())
        self.assertTrue((self.output_dir / "components/CursorFollower.tsx").exists())


if __name__ == "__main__":
    unittest.main()



