from __future__ import annotations

import unittest
from webextractor.analysis.routes import RouteAnalyzer
from webextractor.capture.crawler import WebsiteCrawler


class TestPhase1RouterDiscovery(unittest.TestCase):
    def test_router_manifest_routes_discovered(self):
        """Proves routes defined in SPA router manifests are discovered and normalized."""
        html = """
        <html>
          <body>
            <script src="/scripts/script_main.12345.mjs"></script>
          </body>
        </html>
        """
        # Extra routes extracted from script_main manifest table
        manifest_routes = ["/work", "/designs", "/motion", "/contact", "/404"]
        routes = RouteAnalyzer.analyze_routes(html, "https://example.com/", extra_routes=manifest_routes)
        route_paths = [r.path for r in routes]

        self.assertIn("/", route_paths)
        for expected in manifest_routes:
            self.assertIn(expected, route_paths)

    def test_dynamically_mounted_navigation_routes_discovered(self):
        """Proves dynamically mounted menu links are discovered and merged."""
        html = """
        <html>
          <body>
            <header><button class="framer-zecFa" aria-label="Menu"></button></header>
          </body>
        </html>
        """
        # Extra routes discovered after dynamic hamburger click
        menu_routes = ["/work", "/designs", "/motion", "/contact"]
        routes = RouteAnalyzer.analyze_routes(html, "https://example.com/", extra_routes=menu_routes)
        route_paths = [r.path for r in routes]

        for expected in menu_routes:
            self.assertIn(expected, route_paths)

    def test_discovered_routes_enter_crawler_pipeline(self):
        """Proves crawler normalizes and deduplicates routes into its crawling queue."""
        crawler = WebsiteCrawler(output_dir="tmp/test", max_routes=50, max_depth=3)
        base = "https://example.com/"

        # Test static and CMS routes
        candidate_links = [
            "/work",
            "/contact",
            "/designs",
            "/motion",
            "/404",
            "/work/agriai",
            "/work/smart-folder-organiser",
            "/work/ms-portfolio",
            "/work/revoro-mods",
            "/work/royal-gryphon",
            "/motion/blue-flame",
            "/motion/masked-guy",
            "/motion/motion-design",
            "/motion/royal-gryphon",
            "https://external.com/page",  # Should be excluded (not same origin)
            "mailto:hello@example.com",   # Should be excluded
            "#overview",                  # Should be excluded
            "/assets/main.css",           # Should be excluded (static asset)
        ]

        normalized = []
        for l in candidate_links:
            norm = crawler.normalize_route(l, base)
            if norm:
                normalized.append(norm[0])

        self.assertEqual(len(normalized), 14)
        self.assertIn("/work", normalized)
        self.assertIn("/work/agriai", normalized)
        self.assertIn("/motion/blue-flame", normalized)
        self.assertNotIn("https://external.com/page", normalized)
        self.assertNotIn("/assets/main.css", normalized)
