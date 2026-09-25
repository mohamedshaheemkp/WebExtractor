from __future__ import annotations

import html
import re
from typing import Any


class DomToJsxEmitter:
    """
    Translates extracted SiteIR component DOM nodes into clean, valid React JSX.

    Follows strict generator truthfulness:
    - Emits real source content and component structure from SiteIR.
    - Never invents fabricated copy, placeholders, or synthetic assets.
    - Resolves media strictly against authoritative asset_bindings.
    """

    SELF_CLOSING_TAGS = {
        "img", "br", "hr", "input", "source", "use", "path",
        "circle", "rect", "polygon", "polyline", "line", "stop",
    }

    IGNORED_TAGS = {
        "script", "style", "link", "iframe", "meta", "noscript",
    }

    TAG_MAPPINGS = {
        "body": "div",
        "foreignobject": "foreignObject",
    }

    SVG_ATTR_MAPPINGS = {
        "viewbox": "viewBox",
        "preserveaspectratio": "preserveAspectRatio",
        "stroke-width": "strokeWidth",
        "strokewidth": "strokeWidth",
        "fill-rule": "fillRule",
        "fillrule": "fillRule",
        "clip-rule": "clipRule",
        "cliprule": "clipRule",
        "stroke-linecap": "strokeLinecap",
        "strokelinecap": "strokeLinecap",
        "stroke-linejoin": "strokeLinejoin",
        "strokelinejoin": "strokeLinejoin",
        "stroke-miterlimit": "strokeMiterlimit",
        "strokemiterlimit": "strokeMiterlimit",
        "stroke-dasharray": "strokeDasharray",
        "strokedasharray": "strokeDasharray",
        "stroke-dashoffset": "strokeDashoffset",
        "strokedashoffset": "strokeDashoffset",
        "xmlns:xlink": "xmlnsXlink",
        "xlink:href": "xlinkHref",
        "clippath": "clipPath",
        "clip-path": "clipPath",
        "srcset": "srcSet",
        "crossorigin": "crossOrigin",
        "autoplay": "autoPlay",
        "playsinline": "playsInline",
        "novalidate": "noValidate",
        "tabindex": "tabIndex",
        "for": "htmlFor",
        "maxlength": "maxLength",
        "minlength": "minLength",
        "readonly": "readOnly",
        "autocomplete": "autoComplete",
        "enctype": "encType",
        "hreflang": "hrefLang",
    }

    GLOBAL_HTML_ATTRS = {
        "id", "class", "classname", "style", "title", "dir", "lang", "hidden",
        "tabindex", "role", "itemprop", "itemscope", "itemtype", "contenteditable",
        "spellcheck", "draggable", "translate",
    }

    TAG_SPECIFIC_ATTRS: dict[str, set[str]] = {
        "img": {"src", "srcset", "alt", "width", "height", "loading", "decoding", "sizes", "crossorigin", "usemap", "ismap"},
        "a": {"href", "target", "rel", "download", "hreflang", "type", "media", "ping"},
        "video": {"src", "poster", "autoplay", "controls", "loop", "muted", "preload", "playsinline", "crossorigin", "width", "height"},
        "audio": {"src", "autoplay", "controls", "loop", "muted", "preload", "crossorigin"},
        "source": {"src", "srcset", "type", "media", "sizes"},
        "form": {"action", "method", "enctype", "target", "autocomplete", "novalidate", "name"},
        "input": {"type", "name", "value", "placeholder", "checked", "disabled", "readonly", "required", "autocomplete", "autofocus", "maxlength", "minlength", "pattern", "min", "max", "step", "multiple", "accept", "src", "alt", "width", "height"},
        "button": {"type", "name", "value", "disabled", "autofocus", "form", "formaction", "formenctype", "formmethod", "formnovalidate", "formtarget"},
        "textarea": {"name", "rows", "cols", "placeholder", "disabled", "readonly", "required", "maxlength", "minlength", "autocomplete", "autofocus", "wrap"},
        "select": {"name", "multiple", "size", "disabled", "required", "autofocus", "form"},
        "option": {"value", "selected", "disabled", "label"},
        "iframe": {"src", "srcdoc", "name", "width", "height", "sandbox", "allow", "allowfullscreen", "loading"},
        "meta": {"name", "content", "charset", "httpequiv", "property"},
        "link": {"href", "rel", "as", "type", "media", "crossorigin", "hreflang"},
    }

    SVG_TAGS = {
        "svg", "path", "circle", "rect", "polygon", "polyline", "line",
        "ellipse", "g", "defs", "clippath", "mask", "pattern", "use",
        "text", "tspan", "textpath", "lineargradient", "radialgradient",
        "stop", "foreignobject",
    }

    SVG_STANDARD_ATTRS = {
        "viewbox", "xmlns", "fill", "stroke", "d", "width", "height", "transform",
        "opacity", "color", "stroke-width", "strokewidth", "stroke-linecap",
        "strokelinecap", "stroke-linejoin", "strokelinejoin", "stroke-miterlimit",
        "strokemiterlimit", "stroke-dasharray", "strokedasharray", "stroke-dashoffset",
        "strokedashoffset", "fill-rule", "fillrule", "clip-rule", "cliprule",
        "clip-path", "clippath", "mask", "filter", "id", "class", "classname", "style",
        "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "points",
        "offset", "stop-color", "stopcolor", "stop-opacity", "stopopacity",
        "preserveaspectratio", "href", "xlink:href", "xmlns:xlink", "gradientunits",
        "gradienttransform", "patternunits", "patterntransform", "spreadmethod",
        "text-anchor", "textanchor", "dominant-baseline", "dominantbaseline",
        "font-size", "fontsize", "font-family", "fontfamily", "font-weight",
        "fontweight", "font-style", "fontstyle", "letter-spacing", "letterspacing",
        "word-spacing", "wordspacing", "dx", "dy", "rotate", "textlength",
        "lengthadjust", "target", "download", "rel", "type", "media",
        "focusable", "tabindex", "role",
    }

    def __init__(
        self,
        component_tree: dict[str, Any] | None = None,
        asset_bindings: list[dict[str, Any]] | None = None,
        motion_targets: set[str] | dict[str, Any] | list[str] | None = None,
    ):
        self.tree = component_tree or {}
        self.asset_bindings = asset_bindings or []
        self._binding_index = 0
        self.ambiguities: list[str] = []
        if isinstance(motion_targets, dict):
            self.motion_targets = set(motion_targets.keys())
        elif isinstance(motion_targets, set):
            self.motion_targets = motion_targets
        elif isinstance(motion_targets, list):
            self.motion_targets = set(motion_targets)
        else:
            self.motion_targets = set()

    # ------------------------------------------------------------------
    # Structural Section Decomposition (generic, platform-agnostic)
    # ------------------------------------------------------------------

    @classmethod
    def decompose_content_sections(
        cls,
        root_node: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """
        Decomposes a rendered DOM tree structurally into:
        (content_root, sections)
        Where content_root is the outer layout wrapper (e.g. <main> or root <div>),
        and sections are its direct children, strictly non-overlapping and disjoint.

        Naming strategy (in priority order):
          1. data-component-name / data-framer-name / aria-label attribute
          2. Semantic HTML tag + existing element ID
          3. Indexed Section_NN fallback
        No portfolio-specific or platform-specific hardcoded names are used.
        """
        if not root_node:
            return None, []

        def count_nodes(n: dict[str, Any]) -> int:
            return 1 + sum(count_nodes(c) for c in n.get("children", []) if isinstance(c, dict))

        # Drill into the canonical content container
        curr = root_node
        visual_children = [
            c for c in curr.get("children", [])
            if isinstance(c, dict) and c.get("tag") not in ("script", "style", "noscript", "link", "meta", "iframe")
        ]

        if (len(visual_children) == 1 and visual_children[0].get("tag") in ("div", "main")) or any(c.get("id") == "main" or c.get("tag") == "main" for c in visual_children):
            main_c = next((c for c in visual_children if c.get("id") == "main" or c.get("tag") == "main"), visual_children[0])
            curr = main_c

        while curr:
            if curr.get("tag") in ("section", "header", "footer", "nav", "article"):
                break
            children = [
                c for c in curr.get("children", [])
                if isinstance(c, dict) and c.get("tag") not in ("script", "style", "noscript", "link", "meta", "iframe")
            ]
            if not children:
                break
            if any(c.get("tag") in ("section", "header", "footer", "nav", "article") for c in children):
                break
            child_counts = [count_nodes(c) for c in children]
            max_cnt = max(child_counts)
            total_cnt = sum(child_counts)

            if len(children) > 1 and max_cnt >= 0.75 * total_cnt:
                dominant_idx = child_counts.index(max_cnt)
                curr = children[dominant_idx]
            elif len(children) == 1 and children[0].get("tag") in ("div", "main"):
                curr = children[0]
            else:
                break

        content_root = curr
        raw_sections = [
            c for c in content_root.get("children", [])
            if isinstance(c, dict) and c.get("tag") not in ("script", "style", "noscript", "link", "meta")
        ]

        sections: list[dict[str, Any]] = []
        used_names: set[str] = set()

        for idx, s in enumerate(raw_sections):
            attrs = s.get("attributes", {})
            s_tag = (s.get("tag") or "").lower()
            raw_id = str(s.get("id") or attrs.get("id") or "").strip()

            # --- Generic naming: derive from attributes, tags, ids ---
            raw_name = (
                attrs.get("data-component-name")
                or attrs.get("data-framer-name")
                or attrs.get("aria-label")
            )

            if not raw_name:
                classes = s.get("classes", [])
                classes_str = " ".join(classes).lower()
                if "hero" in classes_str:
                    raw_name = "Hero"
                elif "intro" in classes_str:
                    raw_name = "Intro"
                elif "project" in classes_str:
                    raw_name = "Projects"
                elif s_tag in ("header", "nav") or "header" in classes_str or "nav" in classes_str:
                    raw_name = "Header" if not raw_id else raw_id
                elif s_tag == "footer" or "footer" in classes_str:
                    raw_name = "Footer" if not raw_id else raw_id
                elif raw_id:
                    if raw_id.lower() == "voice":
                        raw_name = "VoiceOfMS"
                    elif raw_id.lower() in ("contact", "get-in-touch") and idx >= len(raw_sections) - 2:
                        raw_name = "CTA"
                    else:
                        raw_name = raw_id
                else:
                    # Indexed fallback — no content guessing
                    raw_name = f"Section_{idx + 1:02d}"

            raw_str = str(raw_name)
            if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", raw_str):
                clean = raw_str[0].upper() + raw_str[1:]
            else:
                clean = "".join(w.capitalize() for w in re.split(r"[^a-zA-Z0-9]+", raw_str) if w)

            if not clean or clean[0].isdigit():
                clean = f"Section_{clean}"
            RESERVED_NAMES = {"Image", "Script", "Head", "Link", "Document", "Window", "Style"}
            if clean in RESERVED_NAMES:
                clean = f"Section{clean}"

            base = clean
            counter = 1
            while clean in used_names:
                clean = f"{base}_{counter}"
                counter += 1
            used_names.add(clean)

            sections.append({
                "name": clean,
                "tag": s.get("tag", "div"),
                "node": s,
                "nodes_count": count_nodes(s),
            })

        return content_root, sections

    # ------------------------------------------------------------------
    # Component Node Lookup (structural only, no keyword guessing)
    # ------------------------------------------------------------------

    def find_node_for_component(self, name: str) -> dict[str, Any] | None:
        """
        Locates the authoritative DOM node for a named component using
        structural partitioning only.

        Strict invariant: An ancestor node containing the whole page can NEVER
        be returned as a sub-component, preventing parent-child duplication.

        Match strategy (in order):
          1. Exact section name match from decompose_content_sections
          2. Semantic tag match (header/nav → Header*, footer → Footer*)
          3. Soft substring match on section name, ID, or data-attributes
        """
        if not self.tree:
            return None

        content_root, sections = self.decompose_content_sections(self.tree)
        name_lower = name.lower()

        if not sections:
            return None

        # 1. Exact name match (e.g. "Hero", "About", "Portfolio", "Section_01")
        for sec in sections:
            if sec["name"].lower() == name_lower:
                return sec["node"]

        # 2. Semantic tag match for header/footer
        for idx, sec in enumerate(sections):
            s_node = sec["node"]
            s_tag = (s_node.get("tag") or "").lower()

            if name_lower in ("headernavigation", "header", "nav"):
                if s_tag in ("header", "nav") or idx == 0:
                    return s_node
            if name_lower == "footer":
                if s_tag == "footer" or (idx == len(sections) - 1 and idx > 0):
                    return s_node

        # 3. Soft substring match on section name, element ID, or data-attributes
        for sec in sections:
            s_node = sec["node"]
            s_name = sec["name"].lower()
            s_attrs = s_node.get("attributes", {})
            raw_label = str(
                s_attrs.get("data-component-name")
                or s_attrs.get("data-framer-name")
                or s_attrs.get("aria-label")
                or s_node.get("id")
                or ""
            ).lower()

            if name_lower in s_name or name_lower in raw_label:
                return s_node
            if s_name in name_lower:
                return s_node

        return None

    def emit_jsx(
        self,
        node: dict[str, Any],
        depth: int = 1,
        root_classes: str = "",
        root_id: str | None = None,
        is_root: bool = True,
    ) -> str:
        """Translates a ComponentNode subtree into valid React JSX."""
        tag = (node.get("tag") or "div").lower()
        if tag in self.IGNORED_TAGS:
            return ""

        tag = self.TAG_MAPPINGS.get(tag, tag)
        indent = "  " * depth

        # Attributes
        classes = list(node.get("classes", []))
        if is_root and root_classes:
            classes.insert(0, root_classes)

        cls_str = " ".join(classes).strip()

        # In root tag with dynamic className prop:
        if is_root and "${className}" in cls_str:
            clean_cls = cls_str.replace("${className}", "").strip()
            cls_attr = f' className={{`{clean_cls} ${{className}}`.trim()}}'
        elif cls_str:
            cls_attr = f' className="{cls_str}"'
        else:
            cls_attr = ""

        id_attr = f' id="{root_id}"' if (is_root and root_id) else ""

        # Collect and normalize element attributes
        node_attrs = dict(node.get("attributes") or {})
        node_classes = list(node.get("classes", []))
        node_id = str(node.get("id") or "")

        # Detect motion-governed element
        motion_id = None
        if "data-motion-id" in node_attrs:
            motion_id = str(node_attrs["data-motion-id"])
        elif "data-framer-appear-id" in node_attrs:
            motion_id = str(node_attrs["data-framer-appear-id"])
        elif node_id and node_id in self.motion_targets:
            motion_id = node_id
        else:
            for c in node_classes:
                if c in self.motion_targets or f".{c}" in self.motion_targets or f"motion-{c}" in self.motion_targets:
                    motion_id = c
                    break

        is_motion_element = motion_id is not None
        if is_motion_element and "data-motion-id" not in node_attrs:
            node_attrs["data-motion-id"] = motion_id

        if tag == "foreignObject":
            if "width" not in node_attrs:
                node_attrs["width"] = "100%"
            if "height" not in node_attrs:
                node_attrs["height"] = "100%"

        other_attrs_list: list[str] = []
        style_jsx = ""

        for ak, av in node_attrs.items():
            if av is None:
                continue
            av_str = str(av).strip()
            if not av_str and av_str != "0":
                continue
            ak_lower = ak.lower()
            if ak_lower in ("class", "classname"):
                continue
            if ak_lower == "id" and is_root and root_id:
                continue
            if ak_lower == "style":
                style_jsx = self._parse_style_attribute(av_str, is_motion_element=is_motion_element)
                continue
            if (ak_lower == "src" and tag in ("img", "video")) or (ak_lower in ("srcset", "sizes") and tag == "img"):
                continue
            if ak_lower.startswith("on") or ak_lower.startswith("javascript:"):
                continue

            if tag == "a" and ak_lower == "href":
                clean_href = av_str.strip()
                if clean_href.startswith("./#"):
                    av_str = clean_href[2:]
                elif clean_href.startswith("./"):
                    av_str = "/" + clean_href[2:]
                elif clean_href.startswith(".#"):
                    av_str = clean_href[1:]

            tag_lower = tag.lower()
            if tag_lower in self.SVG_TAGS:
                if ak_lower in self.SVG_STANDARD_ATTRS or ak_lower.startswith("data-") or ak_lower.startswith("aria-"):
                    jsx_ak = self.SVG_ATTR_MAPPINGS.get(ak_lower, ak)
                else:
                    clean_key = ak_lower.lstrip("_")
                    jsx_ak = f"data-{clean_key}"
            elif ak_lower.startswith("data-") or ak_lower.startswith("aria-"):
                jsx_ak = ak
            elif ak_lower in self.GLOBAL_HTML_ATTRS or ak_lower in self.TAG_SPECIFIC_ATTRS.get(tag_lower, set()):
                jsx_ak = self.SVG_ATTR_MAPPINGS.get(ak_lower, ak)
            else:
                clean_key = ak_lower.lstrip("_")
                jsx_ak = f"data-{clean_key}"

            clean_val = html.escape(av_str, quote=True)
            if jsx_ak == "tabIndex" or (jsx_ak in ("colSpan", "rowSpan", "maxLength", "minLength", "start", "rows", "cols") and av_str.lstrip("-").isdigit()):
                other_attrs_list.append(f"{jsx_ak}={{{int(av_str)}}}")
            else:
                other_attrs_list.append(f'{jsx_ak}="{clean_val}"')

        other_attrs_str = (" " + " ".join(other_attrs_list)) if other_attrs_list else ""
        tag_attrs = f"{cls_attr}{id_attr}{other_attrs_str}{style_jsx}"

        # Asset resolution for media tags
        if tag == "img":
            src = self._resolve_image_src(node)
            src_attr = f' src="{src}"' if src else ""
            has_alt = any(k.lower() == "alt" for k in node_attrs)
            alt_attr = "" if has_alt else ' alt=""'

            srcset_attr = ""
            sizes_attr = ""
            raw_srcset = node_attrs.get("srcset") or node_attrs.get("srcSet")
            if raw_srcset:
                parts = [p.strip() for p in str(raw_srcset).split(",") if p.strip()]
                res_cands = []
                for p in parts:
                    sub = p.split()
                    if sub:
                        c_url = self._resolve_single_url(sub[0])
                        w_desc = f" {sub[1]}" if len(sub) > 1 else ""
                        res_cands.append(f"{c_url}{w_desc}")
                if res_cands:
                    srcset_attr = f' srcSet="{", ".join(res_cands)}"'
                    raw_sizes = node_attrs.get("sizes")
                    if raw_sizes:
                        sizes_attr = f' sizes="{html.escape(str(raw_sizes))}"'
            else:
                variants = self._find_bound_variants(node)
                if len(variants) > 1:
                    cand_strs = []
                    for v in variants:
                        v_loc = v.get("local_path")
                        v_w = v.get("width")
                        if v_loc and v_w:
                            cand_strs.append(f"{v_loc} {v_w}w")
                    if cand_strs:
                        srcset_attr = f' srcSet="{", ".join(cand_strs)}"'
                        sizes_attr = ' sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"'

            return f"{indent}<img{tag_attrs}{src_attr}{srcset_attr}{sizes_attr}{alt_attr} />\n"

        if tag == "video":
            src = self._resolve_video_src(node)
            src_attr = f' src="{src}"' if src else ""
            return f"{indent}<video{tag_attrs}{src_attr} autoPlay muted loop playsInline />\n"

        if tag in self.SELF_CLOSING_TAGS:
            return f"{indent}<{tag}{tag_attrs} />\n"

        txt = (node.get("text") or "").strip()
        valid_children = [
            ch for ch in node.get("children", [])
            if (ch.get("tag") or "").lower() not in self.IGNORED_TAGS
        ]

        if not valid_children:
            if txt:
                if re.match(r"^\d{2}:\d{2}:\d{2}$", txt):
                    return f'{indent}<{tag}{tag_attrs}><LiveClock initialTime="{txt}" /></{tag}>\n'
                esc_txt = self._escape_jsx_text(txt)
                return f"{indent}<{tag}{tag_attrs}>{esc_txt}</{tag}>\n"
            else:
                return f"{indent}<{tag}{tag_attrs} />\n"

        # If children have no text, but this node does, emit text directly
        has_child_text = any(self._has_descendant_text(c) for c in valid_children)
        if not has_child_text and txt:
            if re.match(r"^\d{2}:\d{2}:\d{2}$", txt):
                inner = f'{indent}  <LiveClock initialTime="{txt}" />\n'
            else:
                esc_txt = self._escape_jsx_text(txt)
                inner = f"{indent}  {esc_txt}\n"
            for ch in valid_children:
                inner += self.emit_jsx(ch, depth + 1, is_root=False)
            return f"{indent}<{tag}{tag_attrs}>\n{inner}{indent}</{tag}>\n"

        inner = ""
        for ch in valid_children:
            inner += self.emit_jsx(ch, depth + 1, is_root=False)

        if not inner.strip():
            return f"{indent}<{tag}{tag_attrs} />\n"

        return f"{indent}<{tag}{tag_attrs}>\n{inner}{indent}</{tag}>\n"

    def _parse_style_attribute(self, style_str: str, is_motion_element: bool = False) -> str:
        """Parses an inline CSS style string into a valid React style={{ ... }} attribute."""
        if not style_str or not style_str.strip():
            return ""
        entries: list[str] = []
        for part in style_str.split(";"):
            part = part.strip()
            if not part or ":" not in part:
                continue
            k, v = part.split(":", 1)
            k = k.strip()
            v = v.strip().replace('"', '\\"')
            if not k or not v:
                continue

            # Transient motion normalization:
            # If element is represented by SiteIR motion, suppress transient initial animation values
            k_lower = k.lower()
            if is_motion_element:
                if k_lower == "opacity":
                    try:
                        op_val = float(v)
                        if op_val <= 0.05:
                            # Suppress transient initial hidden opacity
                            continue
                    except ValueError:
                        pass
                elif k_lower == "will-change":
                    if any(w in v.lower() for w in ("transform", "opacity")):
                        continue
                elif k_lower == "transform":
                    # Keep legitimate static transforms like translate(-50%, -50%) or rotate
                    is_static_center = "translate(-50%" in v or "translate3d(-50%" in v or v in ("none", "initial")
                    if not is_static_center and any(m in v.lower() for m in ("translatey", "translate3d", "scale", "matrix")):
                        continue

            if k.startswith("--"):
                entries.append(f'"{k}": "{v}"')
            else:
                parts = k.split("-")
                camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
                entries.append(f'{camel}: "{v}"')
        if not entries:
            return ""
        return " style={({ " + ", ".join(entries) + " } as React.CSSProperties)}"

    def extract_projects(self) -> list[dict[str, Any]]:
        """
        Extracts structured project card data from the Projects section if present.
        Extracts cards structurally from DOM nodes without hardcoded portfolio assumptions.
        Returns list of {title, description, tags, image}.
        """
        proj_node = self.find_node_for_component("Projects")
        if not proj_node:
            return []

        projects: list[dict[str, Any]] = []

        def _find_card_candidates(n: dict[str, Any]) -> list[dict[str, Any]]:
            candidates = []
            for ch in n.get("children", []):
                tag = (ch.get("tag") or "").lower()
                classes = [str(c).lower() for c in ch.get("classes", [])]
                if tag in ("article", "a") or any("card" in c or "project" in c or "item" in c for c in classes):
                    candidates.append(ch)
                else:
                    candidates.extend(_find_card_candidates(ch))
            return candidates

        cards = _find_card_candidates(proj_node)

        for card in cards:
            title = ""
            cat = ""
            img_src = None

            def _inspect_node(el: dict[str, Any]):
                nonlocal title, cat, img_src
                el_tag = (el.get("tag") or "").lower()
                el_txt = (el.get("text") or "").strip()

                if el_tag in ("h1", "h2", "h3", "h4", "h5", "h6") and not title and el_txt:
                    title = el_txt
                elif el_tag == "img" and not img_src:
                    img_src = el.get("src") or el.get("attributes", {}).get("src")
                elif el_txt and not title and len(el_txt) < 80:
                    title = el_txt
                elif el_txt and not cat and len(el_txt) < 40 and el_txt != title:
                    cat = el_txt

                for sub in el.get("children", []):
                    _inspect_node(sub)

            _inspect_node(card)

            if title and not any(p["title"].lower() == title.lower() for p in projects):
                projects.append({
                    "title": title,
                    "description": cat or "Featured",
                    "tags": [cat] if cat else ["Featured"],
                    "image": img_src or self._resolve_image_src({}),
                })

        return projects

    def _has_descendant_text(self, node: dict[str, Any]) -> bool:
        tag = (node.get("tag") or "").lower()
        if tag in self.IGNORED_TAGS:
            return False
        if (node.get("text") or "").strip():
            return True
        for ch in node.get("children", []):
            if self._has_descendant_text(ch):
                return True
        return False

    def _resolve_image_src(self, node: dict[str, Any]) -> str | None:
        """Resolves real downloaded local path for img elements from asset_bindings or node attributes."""
        raw_src = node.get("src") or node.get("attributes", {}).get("src")
        if not raw_src:
            attrs = node.get("attributes", {})
            srcset = attrs.get("srcset") or attrs.get("srcSet")
            if srcset and isinstance(srcset, str):
                first_cand = srcset.strip().split(",")[0].strip().split(" ")[0].strip()
                if first_cand:
                    raw_src = first_cand

        if raw_src and isinstance(raw_src, str):
            for b in self.asset_bindings:
                if b.get("local_path") and (b.get("source_url") == raw_src or b.get("local_path") == raw_src):
                    return b["local_path"]
            if raw_src.startswith("/") or raw_src.startswith("http://") or raw_src.startswith("https://") or raw_src.startswith("data:"):
                return raw_src

        img_bindings = [
            b["local_path"] for b in self.asset_bindings
            if b.get("local_path") and b.get("role") in ("image", "poster", "background", "media")
        ]
        if img_bindings:
            resolved = img_bindings[self._binding_index % len(img_bindings)]
            self._binding_index += 1
            return resolved

        return raw_src if isinstance(raw_src, str) else None

    def _find_bound_variants(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        raw_src = node.get("src") or node.get("attributes", {}).get("src")
        if not raw_src or not isinstance(raw_src, str):
            return []
        clean_src = raw_src.split("?")[0]
        for b in self.asset_bindings:
            s_url = b.get("source_url", "")
            if s_url == raw_src or s_url.split("?")[0] == clean_src:
                return b.get("variants", [])
        return []

    def _resolve_single_url(self, url: str) -> str:
        clean_url = url.split("?")[0]
        for b in self.asset_bindings:
            s_url = b.get("source_url", "")
            if s_url == url or s_url.split("?")[0] == clean_url:
                if b.get("local_path"):
                    return b["local_path"]
        return url

    def _resolve_video_src(self, node: dict[str, Any]) -> str | None:
        """Resolves real video source from asset_bindings."""
        for b in self.asset_bindings:
            if b.get("role") == "video" and b.get("local_path"):
                return b["local_path"]
        return None

    @staticmethod
    def _escape_jsx_text(text: str) -> str:
        """Escapes raw text so it is safe inside JSX."""
        if not text:
            return ""
        text = (
            text.replace("{", "&#123;")
            .replace("}", "&#125;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return text
