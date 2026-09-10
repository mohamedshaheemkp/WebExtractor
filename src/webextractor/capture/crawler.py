from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from .behavior import BehaviorProbe
from .browser import BrowserCapture
from .multi_viewport import MultiViewportCapture
from .snapshot import SnapshotWriter


class WebsiteCrawler:
    """
    Universal multi-route website crawler.
    Discovers same-origin routes from DOM links, normalizes and deduplicates them,
    and captures HTML, screenshots, network requests, and DOM ASTs independently.
    """

    STATIC_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
        ".mp4", ".webm", ".ogv", ".mp3", ".wav",
        ".css", ".js", ".mjs", ".map",
        ".pdf", ".zip", ".tar", ".gz", ".rar",
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".xml", ".json", ".txt",
    }

    def __init__(
        self,
        output_dir: str | Path,
        max_routes: int = 10,
        max_depth: int = 2,
        same_origin: bool = True,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.max_routes = max_routes
        self.max_depth = max_depth
        self.same_origin = same_origin
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []

    def normalize_route(self, raw_url: str, base_url: str) -> tuple[str, str] | None:
        """
        Normalizes a discovered URL or path relative to base_url.
        Returns (route_path, clean_full_url) or None if invalid/disallowed.
        Example: ('/work', 'https://example.com/work')
        """
        if not raw_url or not isinstance(raw_url, str):
            return None

        clean_raw = raw_url.strip()
        if not clean_raw or clean_raw.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            return None

        # Resolve relative links
        full_url = urljoin(base_url, clean_raw)
        parsed = urlparse(full_url)

        if parsed.scheme not in ("http", "https"):
            return None

        # Check same origin
        if self.same_origin:
            base_parsed = urlparse(base_url)
            if parsed.netloc.lower() != base_parsed.netloc.lower():
                return None

        # Normalize path
        path = parsed.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        # Check static file extensions
        path_lower = path.lower()
        if any(path_lower.endswith(ext) for ext in self.STATIC_EXTENSIONS):
            return None

        clean_full_url = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))

        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if re.search(pattern, path, re.IGNORECASE) or re.search(pattern, clean_full_url, re.IGNORECASE):
                return None

        # Check include patterns
        if self.include_patterns:
            matched = any(
                re.search(pattern, path, re.IGNORECASE) or re.search(pattern, clean_full_url, re.IGNORECASE)
                for pattern in self.include_patterns
            )
            if not matched:
                return None

        return path, clean_full_url

    async def crawl(
        self,
        url: str,
    ) -> dict[str, Any]:

        browser = BrowserCapture(
            self.output_dir,
        )

        try:
            await browser.start()

            norm_root = self.normalize_route(url, url)
            root_route = norm_root[0] if norm_root else "/"
            root_url = norm_root[1] if norm_root else url

            queue: deque[tuple[str, str, int]] = deque([(root_url, root_route, 0)])
            visited_routes: set[str] = set()
            captured_pages: list[dict[str, Any]] = []
            all_requests: list[dict[str, Any]] = []

            while queue and len(captured_pages) < self.max_routes:
                cur_url, cur_route, cur_depth = queue.popleft()

                if cur_route in visited_routes:
                    continue
                visited_routes.add(cur_route)

                slug = "desktop" if cur_route == "/" else re.sub(r"[^a-zA-Z0-9_\-]", "_", cur_route.strip("/"))
                screenshot_name = f"{slug}.png"

                try:
                    page_capture = await browser.capture(cur_url, screenshot_name=screenshot_name)
                except Exception:
                    continue

                page_capture["route"] = cur_route
                page_capture["slug"] = slug
                captured_pages.append(page_capture)
                all_requests.extend(page_capture.get("requests", []))

                # Queue discovered links if within depth limit
                if cur_depth < self.max_depth:
                    for link in page_capture.get("discovered_links", []):
                        norm = self.normalize_route(link, cur_url)
                        if norm:
                            next_route, next_url = norm
                            if next_route not in visited_routes:
                                queue.append((next_url, next_route, cur_depth + 1))

            if not captured_pages:
                raise RuntimeError(f"Failed to capture any pages from {url}")

            primary_capture = captured_pages[0]

            # Capture responsive viewports on primary page
            if browser.context:
                multi_vp = MultiViewportCapture(self.output_dir)
                vp_results = await multi_vp.capture_all(browser.context, root_url)
                primary_capture["viewports"] = vp_results.get("viewports", {})
                primary_capture["responsive_rules"] = vp_results.get("responsive_rules", [])

                # Run Behavioral Evidence Probe on root page
                try:
                    probe_page = await browser.context.new_page()
                    await probe_page.goto(root_url, wait_until="domcontentloaded", timeout=30_000)
                    await probe_page.wait_for_timeout(2000)
                    probe = BehaviorProbe()
                    discovered_interactions = await probe.probe_page(probe_page)
                    primary_capture["interactions"] = discovered_interactions
                    await probe_page.close()
                except Exception:
                    primary_capture["interactions"] = []
            else:
                primary_capture["viewports"] = {}
                primary_capture["responsive_rules"] = []
                primary_capture["interactions"] = []

            primary_capture["pages"] = captured_pages
            primary_capture["routes"] = [p["route"] for p in captured_pages]
            primary_capture["requests"] = all_requests

            writer = SnapshotWriter(
                self.output_dir,
            )

            snapshot_dir = writer.write(
                primary_capture,
            )

            primary_capture["snapshot_dir"] = str(
                snapshot_dir
            )

            return primary_capture

        finally:
            await browser.close()

