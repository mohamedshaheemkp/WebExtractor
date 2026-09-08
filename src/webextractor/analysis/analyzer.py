from __future__ import annotations

import re
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
from .source_css import extract_relevant_css
from .animations import AnimationExtractor


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
        if (not rendered_dom or not rendered_dom.get("children")) and html:
            rendered_dom = self._html_to_dom_tree(html)
        elif rendered_dom and html:
            self._enrich_dom_attributes(rendered_dom, html)

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

        # Extract relevant CSS and font faces for referenced DOM classes
        referenced_classes: set[str] = set()
        def _collect_classes(n: dict[str, Any] | None):
            if not n or not isinstance(n, dict):
                return
            for c in n.get("classes", []):
                referenced_classes.add(c)
            for ch in n.get("children", []):
                _collect_classes(ch)

        if component_tree:
            _collect_classes(component_tree)

        font_families = [f.get("name") for f in typography.get("font_families", [])] if typography else []
        component_styles["source_rules"] = extract_relevant_css(
            html_content=html,
            referenced_classes=referenced_classes,
            font_families=font_families,
            external_css=capture.get("css", ""),
        )

        # Extract animations and interactive metadata
        animations = AnimationExtractor.extract_animations(
            html_content=html,
            css_content=capture.get("css", ""),
        )

        # Extract collection items (projects, posts, products) from structured sub-routes/links in HTML
        if html:
            try:
                from bs4 import BeautifulSoup
                import re
                soup_links = BeautifulSoup(html, "html.parser")
                discovered_items = []
                content_prefix_pattern = re.compile(
                    r"/(work|projects|portfolio|case-studies|case-study|blog|posts|articles|products|services)/([^/#?]+)/?$",
                    re.IGNORECASE,
                )

                for a in soup_links.find_all("a"):
                    href = a.get("href", "")
                    match = content_prefix_pattern.search(href)
                    if match:
                        slug = match.group(2).strip()
                        title_elem = a.find(["h1", "h2", "h3", "h4", "h5", "h6"])
                        p_elems = a.find_all("p")
                        title = title_elem.get_text(strip=True) if title_elem else ""
                        cat = p_elems[0].get_text(strip=True) if p_elems else ""
                        if not title:
                            parts = a.get_text("|", strip=True).split("|")
                            title = parts[0].strip() if parts else slug.replace("-", " ").title()
                            cat = parts[1].strip() if len(parts) > 1 else ""
                        img = a.find("img")
                        img_src = img.get("src") if img else None
                        if title and not any(p.get("slug") == slug for p in discovered_items):
                            discovered_items.append({
                                "slug": slug,
                                "title": title,
                                "category": cat or "Featured",
                                "description": f"{title} — {cat}" if cat else title,
                                "image": img_src,
                                "tags": [cat] if cat else ["Featured"],
                            })
                if discovered_items:
                    data["projects"] = discovered_items
            except Exception:
                pass

        # Propagate image bindings into project datasets (strictly real paths or None)
        project_bindings = [
            b for b in asset_bindings
            if b.component in ("ProjectCard", "Projects") and b.role == "image" and b.resolved and b.local_path
        ]
        for idx, proj in enumerate(data.get("projects", [])):
            if idx < len(project_bindings):
                proj["image"] = project_bindings[idx].local_path
            elif not proj.get("image"):
                proj["image"] = None

        captured_pages = capture.get("pages", [])
        if captured_pages:
            pages = []
            for cp in captured_pages:
                cp_route = cp.get("route", "/")
                cp_dom = cp.get("dom")
                if cp_route == "/":
                    pages.append({
                        "route": "/",
                        "title": cp.get("title") or dom.get("title", "Home"),
                        "components": page_components,
                        "dom": cp_dom or rendered_dom,
                    })
                else:
                    # Use captured DOM to infer actual page structure
                    sub_components: list[dict[str, Any]] = []
                    if cp_dom:
                        from webextractor.generator.dom_emitter import DomToJsxEmitter
                        _, sub_sections = DomToJsxEmitter.decompose_content_sections(cp_dom)
                        for si, sec in enumerate(sub_sections):
                            s_tag = (sec.get("tag") or "").lower()
                            sec_type = "header" if (si == 0 and s_tag in ("header", "nav", "div")) else (
                                "footer" if (si == len(sub_sections) - 1 and s_tag in ("footer", "div")) else "section"
                            )
                            sub_components.append({
                                "name": sec["name"],
                                "type": sec_type,
                                "tag": sec["tag"],
                            })
                    if not sub_components:
                        # Fallback when no DOM captured for this route
                        sub_components = [
                            {"name": "Header", "type": "header"},
                            {"name": "Section_01", "type": "section"},
                            {"name": "Footer", "type": "footer"},
                        ]
                    pages.append({
                        "route": cp_route,
                        "title": cp.get("title", ""),
                        "dom": cp_dom,
                        "components": sub_components,
                    })
        else:
            pages = [
                {
                    "route": "/",
                    "components": page_components,
                    "dom": rendered_dom,
                }
            ]
            for r in routes:
                if r not in ("/", "") and not r.startswith("http"):
                    pages.append({
                        "route": r if r.startswith("/") else f"/{r}",
                        "components": [
                            {"name": "Header", "type": "header"},
                            {"name": "Section_01", "type": "section"},
                            {"name": "Footer", "type": "footer"},
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
        setattr(site_model, "animations", animations)

        return site_model



    def _infer_page_components(
        self,
        dom: dict[str, Any],
        rendered_dom: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Infers top-level page components with child relationships in logical rendering order."""
        if rendered_dom:
            from webextractor.generator.dom_emitter import DomToJsxEmitter
            content_root, sections = DomToJsxEmitter.decompose_content_sections(rendered_dom)
            if sections:
                result = []
                for idx, sec in enumerate(sections):
                    tag = (sec.get("tag") or "").lower()
                    sec_type = "header" if (idx == 0 and tag in ("header", "nav", "div")) else (
                        "footer" if (idx == len(sections) - 1 and tag in ("footer", "div")) else "section"
                    )
                    item: dict[str, Any] = {
                        "name": sec["name"],
                        "type": sec_type,
                        "tag": sec["tag"],
                    }

                    # Detect repeating-item data patterns from section content
                    s_name_lower = sec["name"].lower()
                    s_node = sec.get("node", {})
                    s_attrs = s_node.get("attributes", {}) if isinstance(s_node, dict) else {}
                    label = str(
                        s_attrs.get("data-component-name")
                        or s_attrs.get("aria-label")
                        or s_node.get("id")
                        or ""
                    ).lower()
                    combined = f"{s_name_lower} {label}"

                    if any(kw in combined for kw in ("project", "portfolio", "work", "case")):
                        item["children"] = ["ProjectCard"]
                        item["data_key"] = "projects"
                    elif any(kw in combined for kw in ("service", "capabil", "feature")):
                        item["children"] = ["CapabilityItem"]
                        item["data_key"] = "capabilities"
                    elif any(kw in combined for kw in ("experience", "journey", "timeline")):
                        item["children"] = ["JourneyItem"]
                        item["data_key"] = "journey"
                    elif any(kw in combined for kw in ("tool", "stack", "skill", "tech")):
                        item["children"] = ["ToolkitItem"]
                        item["data_key"] = "toolkit"
                    elif sec_type == "header":
                        item["children"] = ["NavItem"]

                    result.append(item)
                return result

        # Fallback: infer from raw HTML structure (no rendered DOM available)
        sections_raw = dom.get("sections", [])
        headings = [h.get("text", "").strip() for h in dom.get("headings", [])]

        detected: list[dict[str, Any]] = []

        # Always emit a header at the top
        detected.append({
            "name": "Header",
            "type": "header",
            "children": ["NavItem"],
        })

        # Derive section names from headings when possible
        for idx, heading in enumerate(headings[:10]):
            if not heading:
                continue
            # Create a clean component name from the heading text
            clean = "".join(w.capitalize() for w in re.split(r"[^a-zA-Z0-9]+", heading) if w)
            if not clean or clean[0].isdigit():
                clean = f"Section{clean}"
            if len(clean) > 40:
                clean = clean[:40]
            detected.append({
                "name": clean,
                "type": "section",
            })

        # If no headings found, add a generic content section
        if len(detected) == 1:
            detected.append({
                "name": "Section_01",
                "type": "section",
            })

        # Always emit a footer at the bottom
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

    def _enrich_dom_attributes(self, rendered_dom: dict[str, Any], html: str) -> None:
        """Enriches raw captured DOM nodes with attributes (viewBox, width, height, style, etc.) from HTML."""
        if not rendered_dom or not html:
            return
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            body_tag = soup.body
            if not body_tag:
                return

            def _enrich(node: dict[str, Any], elem: Any):
                if not elem or not hasattr(elem, "attrs"):
                    return
                attrs = dict(node.get("attributes") or {})
                for k, v in elem.attrs.items():
                    attr_name = "viewBox" if k.lower() == "viewbox" else k
                    if isinstance(v, list):
                        v = " ".join(v)
                    if attr_name not in ("class",):
                        attrs[attr_name] = str(v)
                if attrs:
                    node["attributes"] = attrs

                elem_children = [c for c in elem.children if hasattr(c, "name") and c.name]
                node_children = node.get("children", [])
                for nc, ec in zip(node_children, elem_children):
                    _enrich(nc, ec)

            _enrich(rendered_dom, body_tag)
        except Exception:
            pass

    def _html_to_dom_tree(self, html: str) -> dict[str, Any]:
        """Constructs a full DOM tree dictionary from HTML when browser snapshot is absent or empty."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            body = soup.body
            if not body:
                return {"tag": "body", "children": []}

            def _convert(elem: Any, depth: int = 0) -> dict[str, Any] | None:
                if not elem or depth > 20:
                    return None
                tag = elem.name
                classes = elem.get("class", [])
                if isinstance(classes, str):
                    classes = classes.split()
                element_id = elem.get("id")
                child_tags = [c for c in elem.children if hasattr(c, "name") and c.name]
                text = elem.get_text(" ", strip=True)[:500] if not child_tags else ""
                attrs: dict[str, str] = {}
                for k, v in elem.attrs.items():
                    attr_name = "viewBox" if k.lower() == "viewbox" else k
                    if isinstance(v, list):
                        v = " ".join(v)
                    if attr_name not in ("class", "id"):
                        attrs[attr_name] = str(v)

                children = []
                for child in elem.children:
                    if hasattr(child, "name") and child.name and child.name not in ("script", "style", "noscript"):
                        c_node = _convert(child, depth + 1)
                        if c_node:
                            children.append(c_node)

                return {
                    "tag": tag,
                    "id": element_id,
                    "classes": classes,
                    "text": text,
                    "attributes": attrs,
                    "children": children,
                    "styles": {},
                }

            return _convert(body, 0) or {"tag": "body", "children": []}
        except Exception:
            return {"tag": "body", "children": []}


