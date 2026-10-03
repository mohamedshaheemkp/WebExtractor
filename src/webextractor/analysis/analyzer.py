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
from .interactions import InteractionAnalyzer


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
        # Merge in every route the crawler actually visited (BFS across depth,
        # not just links found on the homepage) so pages reachable only from
        # sub-pages still get generated.
        crawled_routes = capture.get("routes", [])
        if crawled_routes:
            routes = sorted(set(routes) | {r for r in crawled_routes if r})

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
            pages=capture.get("pages", []),
            overlay=capture.get("overlay"),
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

        # Extract relevant CSS and font faces for referenced DOM classes across all viewports
        referenced_classes: set[str] = set()
        def _collect_classes(n: dict[str, Any] | None):
            if not n or not isinstance(n, dict):
                return
            for c in n.get("classes", []):
                if c:
                    referenced_classes.add(c)
            for ch in n.get("children", []):
                _collect_classes(ch)

        if component_tree:
            _collect_classes(component_tree)
        if rendered_dom:
            _collect_classes(rendered_dom)

        vps = capture.get("viewports", {})
        if isinstance(vps, dict):
            for vp_data in vps.values():
                if isinstance(vp_data, dict):
                    if vp_data.get("dom"):
                        _collect_classes(vp_data["dom"])
                    m_state = vp_data.get("menu_state")
                    if isinstance(m_state, dict) and m_state.get("open_dom"):
                        _collect_classes(m_state["open_dom"])

        if html:
            for cls_match in re.findall(r'class=["\']([^"\']+)["\']', html):
                for part in cls_match.split():
                    if part:
                        referenced_classes.add(part)

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

        # Merge generic scroll-reveal detections (from pre/post-scroll style
        # diffing in the browser capture) into the appear-animation map.
        # This covers reveal animations regardless of which library the
        # source site used (Framer's own runtime is still handled above via
        # data-framer-appear-id; this fills the gap for everything else).
        reveal_candidates = capture.get("reveal_candidates", [])
        if reveal_candidates:
            appear = animations.setdefault("appear_animations", {})
            triggers = animations.setdefault("motion_triggers", [])
            default_duration = animations.get("default_transition_duration", 0.6)
            site_easing = (
                animations.get("timing_function")
                or animations.get("default_timing_function")
                or animations.get("default_easing")
            )
            for rc in reveal_candidates:
                rid = rc.get("id")
                if not rid or rid in appear:
                    continue
                initial = rc.get("initial", {}) or {}
                rc_dur = rc.get("duration")
                rc_easing = rc.get("easing") or site_easing

                dur_val = default_duration
                if rc_dur is not None:
                    d_m = re.search(r"(?:^|[^\w.])([0-9]*\.?[0-9]+)(m?s)?(?=[^\w]|$)", str(rc_dur))
                    if d_m:
                        v = float(d_m.group(1))
                        dur_val = v / 1000.0 if (d_m.group(2) and d_m.group(2).lower() == "ms") else v

                trans_cfg: dict[str, Any] = {
                    "duration": round(dur_val, 2),
                    "type": "tween",
                }
                if rc_easing:
                    trans_cfg["timing_function"] = rc_easing
                    trans_cfg["easing"] = rc_easing
                    trans_cfg["ease"] = rc_easing

                cfg = {
                    "initial": {
                        "opacity": round(float(initial.get("opacity", 1)), 3),
                        "y": round(float(initial.get("y", 0)), 1),
                        "x": round(float(initial.get("x", 0)), 1),
                    },
                    "animate": {"opacity": 1, "y": 0, "x": 0},
                    "transition": trans_cfg,
                    "trigger": "in_view",
                }
                appear[rid] = cfg
                triggers.append({
                    "trigger": "in_view",
                    "target": f'[data-motion-id="{rid}"]',
                    "id": rid,
                    **cfg,
                })

        # Extract DOM-level computed transitions (Path 2: DOM computed-style path)
        if capture.get("dom"):
            self._extract_dom_transitions(capture.get("dom"), animations)
        for p in capture.get("pages", []):
            if p.get("dom"):
                self._extract_dom_transitions(p.get("dom"), animations)

        # Extract behavioral interactions from probe evidence and DOM/CSS/route clues
        probe_interactions = capture.get("interactions", [])
        interactions = InteractionAnalyzer.analyze_behavioral_interactions(
            probe_interactions=probe_interactions,
            html_content=html,
            css_content=capture.get("css", ""),
            routes=routes,
        )

        # Extract collection items (projects, posts, products) from structured sub-routes/links in HTML
        if html:
            try:
                from bs4 import BeautifulSoup
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
        resp_rules = capture.get("responsive_rules", [])
        if not resp_rules and capture.get("viewports"):
            try:
                from webextractor.capture.multi_viewport import MultiViewportCapture
                mvc = MultiViewportCapture(output_dir="")
                resp_rules = mvc._extract_responsive_rules(capture.get("viewports", {}))
            except Exception:
                pass
        setattr(site_model, "responsive_rules", resp_rules)
        setattr(site_model, "viewports", capture.get("viewports", {}))
        setattr(site_model, "animations", animations)
        setattr(site_model, "interactions", interactions)
        setattr(site_model, "overlay", capture.get("overlay"))

        return site_model



    def _extract_dom_transitions(
        self,
        dom_node: dict[str, Any] | None,
        animations: dict[str, Any],
    ) -> None:
        """
        Traverses captured DOM tree to propagate explicit transition properties
        (especially cubic-bezier, steps, linear, or ease curves) into the animation IR.
        Directly links DOM node -> data-framer-appear-id / data-motion-id -> appear_animations & motion_triggers.
        """
        if not dom_node or not isinstance(dom_node, dict):
            return

        styles = dom_node.get("styles", {}) or {}
        tf = styles.get("transitionTimingFunction")
        dur_str = styles.get("transitionDuration")
        trans_str = styles.get("transition")

        attrs = dom_node.get("attributes", {}) or {}
        framer_appear_id = attrs.get("data-framer-appear-id")
        motion_id = attrs.get("data-motion-id")
        data_aos = attrs.get("data-aos")

        # 1. Parse duration (supporting .3s, 0.3s, 1.2s, 0s without confusing duration with delay)
        dur_val: float | None = None
        if dur_str:
            d_m = re.search(r"(?:^|[^\w.])([0-9]*\.?[0-9]+)(m?s)?(?=[^\w]|$)", str(dur_str))
            if d_m:
                v = float(d_m.group(1))
                dur_val = v / 1000.0 if (d_m.group(2) and d_m.group(2).lower() == "ms") else v
        elif trans_str:
            trans_no_tf = re.sub(
                r"(cubic-bezier\([^)]+\)|steps\([^)]+\)|step-start|step-end|ease-in-out|ease-in|ease-out|linear|ease)",
                "",
                trans_str,
                flags=re.IGNORECASE,
            )
            times = list(re.finditer(r"(?<![\w.])([0-9]*\.?[0-9]+)(m?s)(?![\w])", trans_no_tf))
            if times:
                v = float(times[0].group(1))
                dur_val = v / 1000.0 if times[0].group(2).lower() == "ms" else v

        # 2. Parse timing function (cubic-bezier, steps, ease-in-out, linear, ease)
        timing_function: str | None = None
        tf_pattern = re.compile(
            r"(cubic-bezier\([^)]+\)|steps\([^)]+\)|step-start|step-end|ease-in-out|ease-in|ease-out|linear|ease)",
            re.IGNORECASE,
        )
        if tf:
            tf_m = tf_pattern.search(str(tf))
            if tf_m:
                timing_function = tf_m.group(0).strip()
        elif trans_str:
            tf_m = tf_pattern.search(trans_str)
            if tf_m:
                timing_function = tf_m.group(0).strip()

        # 3. Determine if intentional transition exists on this element
        has_custom_tf = bool(
            timing_function and timing_function.lower() not in ("none", "initial", "inherit")
        )
        has_nonzero_dur = bool(dur_val is not None and dur_val > 0)
        is_animated_node = bool(framer_appear_id or motion_id or data_aos)

        is_intentional = (
            (has_custom_tf and timing_function.lower() != "ease")
            or has_nonzero_dur
            or (is_animated_node and (timing_function is not None or dur_val is not None))
        )

        if is_intentional:
            node_id = dom_node.get("id")
            raw_classes = [c for c in dom_node.get("classes", []) if not str(c).startswith("motion-")]
            classes = [re.sub(r"[^a-zA-Z0-9_-]", "", str(c)) for c in raw_classes if c]
            classes = [c for c in classes if c]
            tag = dom_node.get("tag", "div")

            if node_id and not str(node_id).isdigit():
                target_sel = f"#{node_id}"
                target_id = str(node_id)
            elif classes:
                target_sel = "." + ".".join(classes[:2])
                target_id = classes[0]
            else:
                target_sel = tag
                target_id = tag

            site_default_dur = animations.get("default_transition_duration", 0.6)
            resolved_dur = dur_val if dur_val is not None else site_default_dur
            resolved_tf = (
                timing_function
                or animations.get("timing_function")
                or animations.get("default_timing_function")
                or animations.get("default_easing")
            )

            if resolved_tf:
                elem_trans = animations.setdefault("element_transitions", {})
                elem_trans[target_sel] = {
                    "duration": round(resolved_dur, 2),
                    "type": "tween",
                    "timing_function": resolved_tf,
                    "easing": resolved_tf,
                    "ease": resolved_tf,
                }

                # Update site default timing function if a custom curve was detected
                if resolved_tf.lower() not in ("ease", "linear"):
                    if not animations.get("timing_function") or animations.get("timing_function") in ("ease", "linear"):
                        animations["timing_function"] = resolved_tf
                        animations["default_timing_function"] = resolved_tf
                        animations["default_easing"] = resolved_tf
                        animations["easing"] = resolved_tf
                        animations["ease"] = resolved_tf

            # 4. Propagate into appear_animations (Requirement 6)
            appear = animations.setdefault("appear_animations", {})
            candidate_ids = [framer_appear_id, motion_id, target_id, node_id]
            for cid in candidate_ids:
                if cid and cid in appear:
                    appear[cid].setdefault("transition", {})
                    if resolved_tf:
                        appear[cid]["transition"]["timing_function"] = resolved_tf
                        appear[cid]["transition"]["easing"] = resolved_tf
                        appear[cid]["transition"]["ease"] = resolved_tf
                    if dur_val is not None and dur_val > 0:
                        appear[cid]["transition"]["duration"] = round(dur_val, 2)

            if framer_appear_id and framer_appear_id not in appear:
                appear[framer_appear_id] = {
                    "initial": {"opacity": 0, "y": 20},
                    "animate": {"opacity": 1, "y": 0},
                    "transition": {
                        "duration": round(resolved_dur, 2),
                        "type": "tween",
                        "timing_function": resolved_tf,
                        "easing": resolved_tf,
                        "ease": resolved_tf,
                    },
                    "variants": {},
                }

            # 5. Propagate into motion_triggers (Requirement 7)
            triggers = animations.setdefault("motion_triggers", [])
            trigger_updated = False
            for trg in triggers:
                trg_target = trg.get("target", "")
                trg_id = trg.get("id")
                matches = (
                    (framer_appear_id and (framer_appear_id == trg_id or framer_appear_id in trg_target))
                    or (motion_id and (motion_id == trg_id or motion_id in trg_target))
                    or (node_id and f"#{node_id}" in trg_target)
                    or (target_sel and target_sel == trg_target)
                )
                if matches:
                    trigger_updated = True
                    trg.setdefault("transition", {})
                    if resolved_tf:
                        trg["transition"]["timing_function"] = resolved_tf
                        trg["transition"]["easing"] = resolved_tf
                        trg["transition"]["ease"] = resolved_tf
                    if dur_val is not None and dur_val > 0:
                        trg["transition"]["duration"] = round(dur_val, 2)

            # Do not append appear animations to motion_triggers if they already exist in appear_animations
            already_in_appear = (
                (framer_appear_id and framer_appear_id in appear)
                or (motion_id and motion_id in appear)
            )
            if not trigger_updated and not already_in_appear and (framer_appear_id or motion_id):
                target = (
                    f'[data-framer-appear-id="{framer_appear_id}"]'
                    if framer_appear_id
                    else f'[data-motion-id="{motion_id}"]'
                )
                triggers.append({
                    "trigger": "mount" if framer_appear_id else "in_view",
                    "target": target,
                    "id": framer_appear_id or motion_id,
                    "adapter": "analyzer",
                    "initial": {"opacity": 0, "y": 20},
                    "animate": {"opacity": 1, "y": 0},
                    "transition": {
                        "duration": round(resolved_dur, 2) if resolved_dur > 0 else 0.6,
                        "type": "tween",
                        "timing_function": resolved_tf,
                        "easing": resolved_tf,
                        "ease": resolved_tf,
                    },
                    "variants": {},
                })

        for child in dom_node.get("children", []):
            self._extract_dom_transitions(child, animations)

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
                    c_name = "HeaderNavigation" if sec["name"] == "Header" and sec_type == "header" else sec["name"]
                    item: dict[str, Any] = {
                        "name": c_name,
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


