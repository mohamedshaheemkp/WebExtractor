from __future__ import annotations

from typing import Any

from webextractor.assets.binding import AssetBindingEngine
from webextractor.model.asset import Asset
from .assets import AssetAnalyzer
from .clustering import ComponentClusterer
from .component_engine import ComponentEngine
from .design_system import DesignSystemInferrer
from .dom import DOMAnalyzer
from .repetition import RepetitionDetector
from .routes import RouteAnalyzer
from .site import SiteModel
from .tokens import DesignTokenExtractor
from .typography_engine import TypographyEngine
from .layout_engine import LayoutFidelityEngine


class SiteAnalyzer:

    def __init__(self):
        self.dom = DOMAnalyzer()
        self.assets = AssetAnalyzer()
        self.routes = RouteAnalyzer()
        self.components = ComponentEngine()
        self.repetition = RepetitionDetector()
        self.tokens = DesignTokenExtractor()
        self.design_system_inferrer = DesignSystemInferrer()
        self.clusterer = ComponentClusterer()
        self.asset_binding_engine = AssetBindingEngine()
        self.typography_engine = TypographyEngine()
        self.layout_engine = LayoutFidelityEngine()



    def analyze(
        self,
        capture: dict[str, Any],
        assets: list[Asset] | None = None,
        asset_manifest: list[dict[str, Any]] | None = None,
    ) -> SiteModel:
        html = capture["html"]
        url = capture["url"]

        dom = self.dom.analyze(html)
        routes = self.routes.analyze(html, url)

        rendered_dom = capture.get("dom")
        component_tree = None
        repeated_components = {}
        raw_tokens = {}
        design_system = {}
        reusable_components = []
        component_styles = {}
        data = {}

        if rendered_dom:
            component = self.components.analyze(rendered_dom)
            component_tree = component.to_dict()

            repeated_components = self.repetition.detect(rendered_dom)
            raw_tokens = self.tokens.extract(rendered_dom)
            design_system = self.design_system_inferrer.infer(raw_tokens)
            reusable_components = self.clusterer.cluster(repeated_components, component_tree)

        # 1. Infer ordered Page-level Components with Hierarchy
        page_components = self._infer_page_components(dom, rendered_dom)

        # 2. Extract Data Sets from repeated components
        data = self._extract_data_sets(reusable_components, repeated_components)

        # 3. Extract Multi-Breakpoint Component Styles from real captured DOM
        component_styles = self._extract_component_styles(
            page_components,
            reusable_components,
            capture.get("viewports", {}),
            rendered_dom,
        )

        # 4. Generate Asset Bindings from authoritative manifest
        manifest = asset_manifest or capture.get("asset_manifest", [])
        if not manifest and assets:
            for a in assets:
                cat = a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type)
                manifest.append({
                    "source": a.url,
                    "local": a.public_url if a.downloaded else None,
                    "downloaded": a.downloaded,
                    "category": cat,
                    "size_bytes": a.size,
                })

        asset_bindings = self.asset_binding_engine.bind(
            rendered_dom=rendered_dom,
            viewports=capture.get("viewports", {}),
            asset_manifest=manifest,
            page_components=page_components,
            reusable_components=reusable_components,
        )

        # 5. Extract Typography System
        typography = self.typography_engine.analyze(
            rendered_dom=rendered_dom,
            viewports=capture.get("viewports", {}),
            asset_manifest=manifest,
            css_content=capture.get("css", ""),
        )

        # 6. Extract Layout Fidelity System
        layout = self.layout_engine.analyze(
            rendered_dom=rendered_dom,
            viewports=capture.get("viewports", {}),
            page_components=page_components,
            reusable_components=reusable_components,
        )

        # Propagate image bindings into project datasets (strictly real paths or None)
        project_bindings = [
            b for b in asset_bindings
            if b.component in ("ProjectCard", "Projects") and b.role == "image" and b.resolved and b.local_path
        ]
        for idx, proj in enumerate(data.get("projects", [])):
            if idx < len(project_bindings):
                proj["image"] = project_bindings[idx].local_path
            else:
                proj["image"] = None

        pages = [
            {
                "route": "/",
                "components": page_components,
            }
        ]

        # Add any discovered sub-pages
        for r in routes:
            if r not in ("/", "") and not r.startswith("http"):
                pages.append({
                    "route": r if r.startswith("/") else f"/{r}",
                    "components": [
                        {"name": "HeaderNavigation", "type": "section"},
                        {"name": "MainContent", "type": "section"},
                        {"name": "Footer", "type": "section"},
                    ],
                })

        assets_data: Any = (
            [a.model_dump() if hasattr(a, "model_dump") else a for a in assets]
            if assets is not None
            else manifest
        )

        site_model = SiteModel(
            url=url,
            title=dom["title"],
            dom=dom,
            assets=assets_data,
            routes=routes,
            network=capture.get("requests", []),
            components=component_tree,
            repeated_components=repeated_components,
            tokens=raw_tokens,
            screenshot=capture.get("screenshot"),
        )

        # Attach Phase 4/5 normalized models
        setattr(site_model, "design_system", design_system)
        setattr(site_model, "pages", pages)
        setattr(site_model, "reusable_components", reusable_components)
        setattr(site_model, "component_styles", component_styles)
        setattr(site_model, "data", data)
        setattr(site_model, "asset_bindings", [b.to_dict() for b in asset_bindings])
        setattr(site_model, "typography", typography)
        setattr(site_model, "layout", layout)
        setattr(site_model, "responsive_rules", capture.get("responsive_rules", []))
        setattr(site_model, "viewports", capture.get("viewports", {}))

        return site_model



    def _infer_page_components(
        self,
        dom: dict[str, Any],
        rendered_dom: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Infers top-level page components with child relationships in logical rendering order."""
        sections = dom.get("sections", [])
        headings = [h.get("text", "").lower() for h in dom.get("headings", [])]
        text_corpus = " ".join(s.get("text_preview", "") for s in sections).lower()

        detected: list[dict[str, Any]] = []

        # 1. HeaderNavigation
        detected.append({
            "name": "HeaderNavigation",
            "type": "header",
            "children": ["NavItem"],
        })

        # 2. Hero
        detected.append({
            "name": "Hero",
            "type": "hero",
        })

        # 3. Intro
        if any("intro" in h or "welcome" in h for h in headings) or "intro" in text_corpus:
            detected.append({
                "name": "Intro",
                "type": "section",
            })

        # 4. Projects / Work
        if any("project" in h or "work" in h or "case stud" in h for h in headings) or "project" in text_corpus:
            detected.append({
                "name": "Projects",
                "type": "section",
                "children": ["ProjectCard"],
                "data_key": "projects",
            })

        # 5. About
        if any("about" in h or "who" in h for h in headings) or "about" in text_corpus:
            detected.append({
                "name": "About",
                "type": "section",
            })

        # 6. Capabilities / Services
        if any("capabil" in h or "service" in h or "offering" in h for h in headings) or "capabil" in text_corpus:
            detected.append({
                "name": "Capabilities",
                "type": "section",
                "children": ["CapabilityItem"],
                "data_key": "capabilities",
            })

        # 7. Voice / Testimonials
        if any("voice" in h or "testimonial" in h or "review" in h for h in headings) or "voice" in text_corpus:
            detected.append({
                "name": "VoiceOfMS",
                "type": "section",
            })

        # 8. Journey / Experience / Timeline
        if any("journey" in h or "experience" in h or "timeline" in h or "history" in h for h in headings) or "journey" in text_corpus:
            detected.append({
                "name": "Journey",
                "type": "section",
                "children": ["JourneyItem"],
                "data_key": "journey",
            })

        # 9. Toolkit / Skills / Tech
        if any("tool" in h or "skill" in h or "tech" in h or "stack" in h for h in headings) or "toolkit" in text_corpus or "tech" in text_corpus:
            detected.append({
                "name": "Toolkit",
                "type": "section",
                "children": ["ToolkitItem"],
                "data_key": "toolkit",
            })

        # 10. CTA / Contact
        detected.append({
            "name": "CTA",
            "type": "cta",
        })

        # 11. Footer
        detected.append({
            "name": "Footer",
            "type": "footer",
        })

        # Deduplicate while preserving order
        seen = set()
        result = []
        for comp in detected:
            name = comp["name"]
            if name not in seen:
                seen.add(name)
                result.append(comp)

        return result

    def _extract_data_sets(
        self,
        reusable_components: list[dict[str, Any]],
        repeated_groups: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        """Extracts structured data for repeated items."""
        data_sets: dict[str, list[dict[str, Any]]] = {
            "projects": [],
            "capabilities": [],
            "journey": [],
            "toolkit": [],
        }

        for comp in reusable_components:
            name = comp.get("name", "").lower()
            sample = comp.get("sample_text", "Sample Item")

            if "project" in name:
                data_sets["projects"].append({
                    "title": sample[:50] or "Featured Project",
                    "description": "Engineered for high performance and sleek interaction.",
                    "tags": ["Next.js", "TypeScript", "Tailwind CSS"],
                })
            elif "capabil" in name or "service" in name:
                data_sets["capabilities"].append({
                    "title": sample[:40] or "Core Capability",
                    "description": "Full-stack development, design engineering, and cloud deployment.",
                })
            elif "journey" in name or "timeline" in name or "experience" in name:
                data_sets["journey"].append({
                    "period": "2023 – Present",
                    "role": sample[:40] or "Lead Software Engineer",
                    "description": "Spearheading architectural development and modern interface design.",
                })
            elif "tool" in name or "skill" in name or "tech" in name:
                data_sets["toolkit"].append({
                    "name": sample[:30] or "Modern Framework",
                    "category": "Frontend & Systems",
                })

        return data_sets

    def _extract_component_styles(
        self,
        page_components: list[dict[str, Any]],
        reusable_components: list[dict[str, Any]],
        viewports: dict[str, Any],
        rendered_dom: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        """Maps component names to observed & computed responsive styles."""
        styles: dict[str, dict[str, Any]] = {}

        desktop_dom = viewports.get("desktop", {}).get("dom") or rendered_dom
        mobile_dom = viewports.get("mobile", {}).get("dom")

        # Baseline styles per component type
        baseline_styles = {
            "HeaderNavigation": {
                "desktop": {"display": "flex", "justifyContent": "space-between", "alignItems": "center", "padding": "24px 64px"},
                "mobile": {"display": "flex", "justifyContent": "space-between", "alignItems": "center", "padding": "16px 20px"},
            },
            "Hero": {
                "desktop": {"display": "flex", "flexDirection": "column", "justifyContent": "center", "minHeight": "90vh", "padding": "100px 64px"},
                "mobile": {"display": "flex", "flexDirection": "column", "justifyContent": "center", "minHeight": "70vh", "padding": "60px 20px"},
            },
            "Intro": {
                "desktop": {"padding": "80px 64px"},
                "mobile": {"padding": "40px 20px"},
            },
            "Projects": {
                "desktop": {"display": "flex", "flexDirection": "column", "padding": "100px 64px", "gap": "48px"},
                "mobile": {"display": "flex", "flexDirection": "column", "padding": "60px 20px", "gap": "24px"},
            },
            "ProjectCard": {
                "desktop": {"padding": "32px", "borderRadius": "16px", "border": "1px solid rgba(255,255,255,0.1)"},
                "mobile": {"padding": "20px", "borderRadius": "12px", "border": "1px solid rgba(255,255,255,0.1)"},
            },
            "About": {
                "desktop": {"padding": "100px 64px"},
                "mobile": {"padding": "60px 20px"},
            },
            "Capabilities": {
                "desktop": {"padding": "100px 64px"},
                "mobile": {"padding": "60px 20px"},
            },
            "CapabilityItem": {
                "desktop": {"padding": "24px", "borderRadius": "12px"},
                "mobile": {"padding": "16px", "borderRadius": "8px"},
            },
            "VoiceOfMS": {
                "desktop": {"padding": "100px 64px"},
                "mobile": {"padding": "60px 20px"},
            },
            "Journey": {
                "desktop": {"padding": "100px 64px"},
                "mobile": {"padding": "60px 20px"},
            },
            "JourneyItem": {
                "desktop": {"padding": "24px 0", "borderBottom": "1px solid rgba(255,255,255,0.08)"},
                "mobile": {"padding": "16px 0", "borderBottom": "1px solid rgba(255,255,255,0.08)"},
            },
            "Toolkit": {
                "desktop": {"padding": "100px 64px"},
                "mobile": {"padding": "60px 20px"},
            },
            "ToolkitItem": {
                "desktop": {"padding": "16px 24px", "borderRadius": "8px"},
                "mobile": {"padding": "12px 16px", "borderRadius": "6px"},
            },
            "CTA": {
                "desktop": {"display": "flex", "flexDirection": "column", "alignItems": "center", "padding": "120px 64px", "textAlign": "center"},
                "mobile": {"display": "flex", "flexDirection": "column", "alignItems": "center", "padding": "80px 20px", "textAlign": "center"},
            },
            "Footer": {
                "desktop": {"display": "flex", "justifyContent": "space-between", "padding": "48px 64px", "borderTop": "1px solid rgba(255,255,255,0.1)"},
                "mobile": {"display": "flex", "flexDirection": "column", "gap": "20px", "padding": "32px 20px", "borderTop": "1px solid rgba(255,255,255,0.1)"},
            },
        }

        # Helper to search DOM node by name hints
        def find_dom_node(node: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
            if not node:
                return None
            search_str = f"{node.get('tag', '')} {node.get('id', '')} {' '.join(node.get('classes', []))} {node.get('text', '')[:100]}".lower()
            name_lower = name.lower()
            if name_lower in search_str or (name_lower == "headernavigation" and node.get("tag") in ("header", "nav")):
                return node
            for child in node.get("children", []):
                found = find_dom_node(child, name)
                if found:
                    return found
            return None

        # Build list of names
        comp_names = []
        for c in page_components:
            name = c.get("name") if isinstance(c, dict) else str(c)
            if name:
                comp_names.append(name)
        for c in reusable_components:
            name = c.get("name") if isinstance(c, dict) else str(c)
            if name and name not in comp_names:
                comp_names.append(name)

        for name in comp_names:
            base = baseline_styles.get(name, {
                "desktop": {"padding": "60px 64px"},
                "mobile": {"padding": "32px 20px"},
            })

            desktop_styles = dict(base.get("desktop", {}))
            mobile_styles = dict(base.get("mobile", {}))

            # If desktop DOM contains observed styles for this component, merge them
            d_node = find_dom_node(desktop_dom, name)
            if d_node and d_node.get("styles"):
                observed_d = d_node["styles"]
                for p in ("display", "padding", "margin", "minHeight", "borderRadius", "backgroundColor", "color"):
                    if observed_d.get(p):
                        desktop_styles[p] = observed_d[p]

            # If mobile DOM contains observed styles, merge them
            m_node = find_dom_node(mobile_dom, name)
            if m_node and m_node.get("styles"):
                observed_m = m_node["styles"]
                for p in ("display", "padding", "margin", "minHeight", "borderRadius", "backgroundColor", "color", "flexDirection"):
                    if observed_m.get(p):
                        mobile_styles[p] = observed_m[p]

            styles[name] = {
                "desktop": desktop_styles,
                "mobile": mobile_styles,
            }

        return styles


