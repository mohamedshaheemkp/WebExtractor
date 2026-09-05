from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from webextractor.har.entries import HAREntryExtractor
from webextractor.har.normalizer import HARNormalizer
from webextractor.model.asset import Asset, AssetType


class AssetDiscovery:
    """
    Unified asset discovery engine.
    Extracts, normalizes, and classifies candidate assets into canonical Asset objects
    from either live Playwright captures or offline HAR archives.
    """

    @classmethod
    def from_crawler(cls, capture: dict[str, Any], base_url: str = "") -> list[Asset]:
        """
        Discovers all assets from a live crawl capture (network requests, HTML, DOM snapshots).
        """
        effective_base = capture.get("url") or base_url
        discovered_map: dict[str, Asset] = {}

        # 1. Inspect captured network requests
        for req in capture.get("requests", []):
            raw_url = req.get("url", "")
            if not raw_url or raw_url.startswith("data:") or raw_url.startswith("blob:"):
                continue

            clean_url = HARNormalizer.normalize_url(raw_url)
            if not clean_url or clean_url in discovered_map:
                continue

            resource_type = req.get("resource_type", "")
            asset_type = cls._resource_type_to_asset_type(resource_type, clean_url)
            parsed = urlparse(clean_url)
            filename = Path(parsed.path).name if parsed.path else "asset"
            ext = Path(filename).suffix.lstrip(".")

            discovered_map[clean_url] = Asset(
                url=clean_url,
                original_url=raw_url,
                domain=parsed.netloc,
                path=parsed.path,
                filename=filename,
                extension=ext,
                asset_type=asset_type,
            )

        # 2. Inspect HTML markup for tags (img, video, link, script, audio, source)
        html_content = capture.get("html", "")
        if html_content:
            cls._extract_from_html(html_content, effective_base, discovered_map)

        # 3. Inspect rendered DOM for background images and inline styles
        dom = capture.get("dom")
        if dom:
            cls._extract_from_dom_node(dom, effective_base, discovered_map)

        return list(discovered_map.values())

    @classmethod
    def from_har(cls, entries: list[dict[str, Any]]) -> list[Asset]:
        """
        Discovers all assets from recorded HAR entries.
        """
        discovered_map: dict[str, Asset] = {}

        for entry in entries:
            url = HAREntryExtractor.get_url(entry)
            if not url or url.startswith("data:") or url.startswith("blob:"):
                continue

            clean_url = HARNormalizer.normalize_url(url)
            if not clean_url or clean_url in discovered_map:
                continue

            mime = HAREntryExtractor.get_mime_type(entry)
            status = HAREntryExtractor.get_status(entry)
            size = HAREntryExtractor.get_size(entry)
            asset_type = HARNormalizer.classify_asset_type(clean_url, mime)
            parsed = urlparse(clean_url)
            filename = Path(parsed.path).name if parsed.path else "asset"
            ext = Path(filename).suffix.lstrip(".")

            discovered_map[clean_url] = Asset(
                url=clean_url,
                original_url=url,
                domain=parsed.netloc,
                path=parsed.path,
                filename=filename,
                extension=ext,
                asset_type=asset_type,
                mime_type=mime,
                status_code=status,
                size=size,
            )

        return list(discovered_map.values())

    @classmethod
    def _extract_from_html(
        cls, html: str, base_url: str, discovered_map: dict[str, Asset]
    ) -> None:
        soup = BeautifulSoup(html, "html.parser")

        # Images
        for img in soup.find_all("img"):
            src = img.get("src")
            cls._add_candidate_url(src, base_url, AssetType.IMAGE, discovered_map)
            # Check srcset
            srcset = img.get("srcset")
            if srcset:
                for candidate in srcset.split(","):
                    parts = candidate.strip().split()
                    if parts:
                        cls._add_candidate_url(parts[0], base_url, AssetType.IMAGE, discovered_map)

        # Videos & Source
        for vid in soup.find_all(["video", "audio"]):
            cls._add_candidate_url(vid.get("src"), base_url, AssetType.VIDEO, discovered_map)
            cls._add_candidate_url(vid.get("poster"), base_url, AssetType.IMAGE, discovered_map)
            for source in vid.find_all("source"):
                cls._add_candidate_url(source.get("src"), base_url, AssetType.VIDEO, discovered_map)

        # Links (CSS, Fonts, Icons)
        for link in soup.find_all("link"):
            href = link.get("href")
            rel = " ".join(link.get("rel", [])).lower()
            if "stylesheet" in rel:
                cls._add_candidate_url(href, base_url, AssetType.CSS, discovered_map)
            elif "font" in rel or link.get("as") == "font":
                cls._add_candidate_url(href, base_url, AssetType.FONT, discovered_map)
            elif "icon" in rel:
                cls._add_candidate_url(href, base_url, AssetType.IMAGE, discovered_map)

        # Scripts
        for script in soup.find_all("script"):
            src = script.get("src")
            cls._add_candidate_url(src, base_url, AssetType.JAVASCRIPT, discovered_map)

    @classmethod
    def _extract_from_dom_node(
        cls, node: dict[str, Any] | None, base_url: str, discovered_map: dict[str, Asset]
    ) -> None:
        if not node:
            return

        src = node.get("src")
        if src:
            tag = node.get("tag", "")
            a_type = AssetType.VIDEO if tag == "video" else AssetType.IMAGE
            cls._add_candidate_url(src, base_url, a_type, discovered_map)

        poster = node.get("poster")
        if poster:
            cls._add_candidate_url(poster, base_url, AssetType.IMAGE, discovered_map)

        styles = node.get("styles", {})
        bg_img = styles.get("backgroundImage") or styles.get("background-image")
        if bg_img and bg_img != "none":
            match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', bg_img)
            if match:
                cls._add_candidate_url(match.group(1), base_url, AssetType.IMAGE, discovered_map)

        for child in node.get("children", []):
            cls._extract_from_dom_node(child, base_url, discovered_map)

    @classmethod
    def _add_candidate_url(
        cls,
        raw_url: str | None,
        base_url: str,
        asset_type: AssetType,
        discovered_map: dict[str, Asset],
    ) -> None:
        if not raw_url:
            return
        raw_url = raw_url.strip()
        if not raw_url or raw_url.startswith("data:") or raw_url.startswith("blob:"):
            return

        full_url = urljoin(base_url, raw_url)
        clean_url = HARNormalizer.normalize_url(full_url)
        if not clean_url or clean_url in discovered_map:
            return

        parsed = urlparse(clean_url)
        filename = Path(parsed.path).name if parsed.path else "asset"
        ext = Path(filename).suffix.lstrip(".")

        # Refine type based on URL extension
        refined_type = HARNormalizer.classify_asset_type(clean_url)
        if refined_type == AssetType.OTHER:
            refined_type = asset_type

        discovered_map[clean_url] = Asset(
            url=clean_url,
            original_url=raw_url,
            domain=parsed.netloc,
            path=parsed.path,
            filename=filename,
            extension=ext,
            asset_type=refined_type,
        )

    @staticmethod
    def _resource_type_to_asset_type(resource_type: str, url: str) -> AssetType:
        rt = (resource_type or "").lower()
        if rt in ("image", "images"):
            return AssetType.IMAGE
        if rt in ("stylesheet", "css"):
            return AssetType.CSS
        if rt in ("font", "fonts"):
            return AssetType.FONT
        if rt in ("media", "video"):
            return AssetType.VIDEO
        if rt in ("script", "javascript"):
            return AssetType.JAVASCRIPT
        if rt in ("document", "html"):
            return AssetType.HTML
        if rt in ("xhr", "fetch"):
            return AssetType.API

        # Fallback to URL extension classification
        return HARNormalizer.classify_asset_type(url)
