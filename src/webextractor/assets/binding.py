from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass
class AssetBinding:
    """
    Represents a semantic link between a component and an extracted asset.
    """
    asset_id: str
    source_url: str
    local_path: str
    type: str  # "image" | "video" | "font" | "icon"
    role: str  # "background" | "video" | "poster" | "image" | "logo" | "thumbnail" | "avatar"
    component: str  # Target component name, e.g. "Hero", "ProjectCard"
    breakpoint: str | None = None  # "desktop" | "mobile" | None (all)
    resolved: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AssetBindingEngine:
    """
    Analyzes DOM trees and asset manifests to bind extracted assets to
    specific components by semantic role and breakpoint.
    """

    def bind(
        self,
        rendered_dom: dict[str, Any] | None,
        viewports: dict[str, Any],
        asset_manifest: list[dict[str, Any]],
        page_components: list[dict[str, Any]] | list[str],
        reusable_components: list[dict[str, Any]],
    ) -> list[AssetBinding]:
        """
        Creates a deterministic list of AssetBindings linking components to local assets.
        """
        bindings: list[AssetBinding] = []

        # Map source URL -> local asset entry
        manifest_map: dict[str, dict[str, Any]] = {}
        for item in asset_manifest:
            src = item.get("source", "").strip()
            if src:
                manifest_map[src] = item
                # Also index by path without query params for flexible matching
                clean_url = src.split("?")[0]
                manifest_map[clean_url] = item

        # Collect candidate asset nodes from viewports and main DOM
        desktop_dom = viewports.get("desktop", {}).get("dom") or rendered_dom
        mobile_dom = viewports.get("mobile", {}).get("dom")

        # Extract bindings from Desktop DOM
        if desktop_dom:
            self._extract_subtree_bindings(desktop_dom, manifest_map, bindings, breakpoint="desktop")

        # Extract bindings from Mobile DOM (if different or specifically mobile)
        if mobile_dom and mobile_dom != desktop_dom:
            self._extract_subtree_bindings(mobile_dom, manifest_map, bindings, breakpoint="mobile")

        # Ensure page components without extracted DOM images receive appropriate manifest assignments if available
        self._assign_fallback_bindings(bindings, asset_manifest, page_components, reusable_components)

        # Deduplicate bindings deterministically
        unique_bindings: dict[str, AssetBinding] = {}
        for b in bindings:
            key = f"{b.component}_{b.role}_{b.breakpoint or 'all'}_{b.source_url}"
            if key not in unique_bindings:
                unique_bindings[key] = b

        # Return sorted list for strict determinism
        return sorted(
            unique_bindings.values(),
            key=lambda x: (x.component, x.role, x.breakpoint or "", x.asset_id)
        )

    def _extract_subtree_bindings(
        self,
        node: dict[str, Any] | None,
        manifest_map: dict[str, dict[str, Any]],
        bindings: list[AssetBinding],
        breakpoint: str | None,
        current_component: str | None = None,
    ) -> None:
        if not node:
            return

        tag = node.get("tag", "").lower()
        node_id = node.get("id") or ""
        classes = node.get("classes", [])
        combined_ident = f"{tag} {node_id} {' '.join(classes)}".lower()

        # Infer component boundary
        comp = self._infer_component_from_ident(combined_ident) or current_component

        # Check for <img> tag
        src = node.get("src") or node.get("currentSrc")
        if tag == "img" and src:
            role = self._infer_role(comp, "image", combined_ident)
            target_comp = comp or "Hero"
            self._record_binding(bindings, target_comp, src, role, "image", manifest_map, breakpoint)

        # Check for <video> tag
        if tag == "video":
            video_src = node.get("src")
            poster_src = node.get("poster")
            target_comp = comp or "Hero"

            if video_src:
                self._record_binding(bindings, target_comp, video_src, "video", "video", manifest_map, breakpoint)
            if poster_src:
                self._record_binding(bindings, target_comp, poster_src, "poster", "image", manifest_map, breakpoint)

        # Check for CSS background-image
        styles = node.get("styles", {})
        bg_image = styles.get("backgroundImage") or styles.get("background")
        if bg_image and "url(" in str(bg_image):
            bg_url = self._extract_url_from_css(str(bg_image))
            if bg_url:
                target_comp = comp or "Hero"
                self._record_binding(bindings, target_comp, bg_url, "background", "image", manifest_map, breakpoint)

        # Recursively traverse children
        for child in node.get("children", []):
            self._extract_subtree_bindings(child, manifest_map, bindings, breakpoint, comp)

    def _record_binding(
        self,
        bindings: list[AssetBinding],
        component: str,
        source_url: str,
        role: str,
        asset_type: str,
        manifest_map: dict[str, dict[str, Any]],
        breakpoint: str | None,
    ) -> None:
        clean_url = source_url.split("?")[0]
        manifest_item = manifest_map.get(source_url) or manifest_map.get(clean_url)

        local_path = ""
        resolved = False
        if manifest_item and manifest_item.get("local"):
            if manifest_item.get("downloaded") is not False:
                local_path = manifest_item["local"]
                resolved = True

        asset_id = f"{component.lower()}-{role}-{len(bindings)}"

        bindings.append(
            AssetBinding(
                asset_id=asset_id,
                source_url=source_url,
                local_path=local_path,
                type=asset_type,
                role=role,
                component=component,
                breakpoint=breakpoint,
                resolved=resolved,
            )
        )

    def _infer_component_from_ident(self, ident: str) -> str | None:
        if "header" in ident or "nav" in ident:
            return "HeaderNavigation"
        if "hero" in ident:
            return "Hero"
        if "project" in ident or "work" in ident:
            return "ProjectCard" if "card" in ident or "item" in ident else "Projects"
        if "capabil" in ident or "service" in ident:
            return "CapabilityItem" if "card" in ident or "item" in ident else "Capabilities"
        if "journey" in ident or "experience" in ident or "timeline" in ident:
            return "JourneyItem" if "card" in ident or "item" in ident else "Journey"
        if "tool" in ident or "skill" in ident:
            return "ToolkitItem" if "card" in ident or "item" in ident else "Toolkit"
        if "footer" in ident:
            return "Footer"
        return None

    def _infer_role(self, component: str | None, default_role: str, ident: str) -> str:
        if component in ("HeaderNavigation", "Footer") or "logo" in ident or "brand" in ident:
            return "logo"
        if component == "Hero":
            return "background"
        if component in ("ProjectCard", "Projects"):
            return "image"
        if "avatar" in ident or "user" in ident or "profile" in ident or component == "VoiceOfMS":
            return "avatar"
        return default_role

    def _extract_url_from_css(self, css_val: str) -> str | None:
        match = re.search(r'url\([\'"]?(.*?)[\'"]?\)', css_val)
        if match:
            url = match.group(1).strip()
            if url.startswith("http") or url.startswith("/"):
                return url
        return None

    def _assign_fallback_bindings(
        self,
        bindings: list[AssetBinding],
        manifest: list[dict[str, Any]],
        page_components: list[dict[str, Any]] | list[str],
        reusable_components: list[dict[str, Any]],
    ) -> None:
        """
        Guarantees that high-value components (Hero, ProjectCard, HeaderNavigation)
        are mapped to genuinely available downloaded assets when DOM inspection alone does not yield direct links.
        """
        bound_components = {b.component for b in bindings if b.resolved}

        image_assets = [m for m in manifest if m.get("category") == "images" and m.get("downloaded") is not False and m.get("local")]
        video_assets = [m for m in manifest if m.get("category") == "videos" and m.get("downloaded") is not False and m.get("local")]

        # Hero fallback
        if "Hero" not in bound_components:
            if video_assets:
                v = video_assets[0]
                bindings.append(AssetBinding(
                    asset_id="hero-video-0",
                    source_url=v.get("source", ""),
                    local_path=v.get("local", ""),
                    type="video",
                    role="video",
                    component="Hero",
                    resolved=True,
                ))
            elif image_assets:
                img = image_assets[0]
                bindings.append(AssetBinding(
                    asset_id="hero-bg-0",
                    source_url=img.get("source", ""),
                    local_path=img.get("local", ""),
                    type="image",
                    role="background",
                    component="Hero",
                    resolved=True,
                ))

        # ProjectCard fallback
        if "ProjectCard" not in bound_components and len(image_assets) > 1:
            for i, img in enumerate(image_assets[1:4]):
                bindings.append(AssetBinding(
                    asset_id=f"project-img-{i}",
                    source_url=img.get("source", ""),
                    local_path=img.get("local", ""),
                    type="image",
                    role="image",
                    component="ProjectCard",
                    resolved=True,
                ))
