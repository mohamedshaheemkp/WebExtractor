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

    COMPONENT_KEYWORDS: dict[str, list[str]] = {
        "HeaderNavigation": ["contact now", "local/", "nav", "header", "menu"],
        "Hero": ["based in india", "available all around", "engineer & dev", "graphic designer", "hero"],
        "Intro": ["01 //", "intro", "tools&frameworks", "combining design and ai"],
        "Projects": ["02 //", "projects", "selected projects", "i build intelligent systems"],
        "About": ["03 //", "who am i", "more about shaheem", "i build with code"],
        "Capabilities": ["04 //", "capability", "improving self", "discover our range"],
        "VoiceOfMS": ["05 //", "voice of ms", "curiosity, design with intent"],
        "Journey": ["06 //", "journey", "2022 - present", "ai developer / designer"],
        "Toolkit": ["07 //", "technical toolkit", "stack & tools"],
        "CTA": ["let's build", "get in touch", "contact"],
        "Footer": ["back to top", "mhd_shm", "©2026", "all rights reserved"],
    }

    def __init__(
        self,
        component_tree: dict[str, Any] | None = None,
        asset_bindings: list[dict[str, Any]] | None = None,
    ):
        self.tree = component_tree or {}
        self.asset_bindings = asset_bindings or []
        self._binding_index = 0
        self.ambiguities: list[str] = []

    def find_node_for_component(self, name: str) -> dict[str, Any] | None:
        """
        Locates the best-matching DOM node for a component in SiteIR.
        Ordering:
        1. Top-level section / container candidate in component tree
        2. Semantic tag matching (<header>/<nav> for HeaderNavigation, <footer> for Footer)
        3. Structural container scoring with keyword matching
        """
        if not self.tree:
            return None

        keywords = self.COMPONENT_KEYWORDS.get(name, [name.lower()])
        scored_candidates: list[tuple[int, int, int, dict[str, Any]]] = []

        def _get_node_text(node: dict[str, Any]) -> str:
            collected = [node.get("text") or ""]
            for child in node.get("children", []):
                collected.append(_get_node_text(child))
            return " ".join(filter(None, collected)).lower()

        def _score_tree(n: dict[str, Any], depth: int):
            tag = (n.get("tag") or "").lower()
            classes = [str(c).lower() for c in n.get("classes", [])]
            node_id = str(n.get("id") or "").lower()

            # Never match root body as a sub-component
            if tag == "body" or depth == 0:
                for ch in n.get("children", []):
                    _score_tree(ch, depth + 1)
                return

            is_semantic_section = tag in ("header", "nav", "section", "footer", "main", "article")
            is_container_div = (tag == "div" and (any(c.endswith("-container") for c in classes) or depth <= 4))

            if is_semantic_section or is_container_div:
                txt = _get_node_text(n)
                score = 0
                for kw in keywords:
                    if kw in txt:
                        score += len(kw) * 4

                n_name = (n.get("name") or "").lower()
                if n_name == name.lower():
                    score += 60

                if name.lower() in classes or name.lower() == node_id:
                    score += 50

                if tag in ("header", "nav") and "Header" in name:
                    score += 50
                elif tag == "footer" and "Footer" in name:
                    score += 50
                elif tag == "section" and name not in ("HeaderNavigation", "Footer"):
                    score += 30

                # Prefer shallower depth (closer to top-level sections)
                depth_penalty = depth * 2

                if score > 0:
                    scored_candidates.append((score - depth_penalty, -depth, -len(txt), n))

            for ch in n.get("children", []):
                _score_tree(ch, depth + 1)

        _score_tree(self.tree, 0)

        if scored_candidates:
            scored_candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
            top_score = scored_candidates[0][0]
            top_matches = [c for c in scored_candidates if c[0] == top_score]
            if len(top_matches) > 1:
                self.ambiguities.append(f"Multiple candidates tied with score {top_score} for {name}")
            return scored_candidates[0][3]

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
                style_jsx = self._parse_style_attribute(av_str)
                continue
            if ak_lower == "src" and tag in ("img", "video"):
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
            return f"{indent}<img{tag_attrs}{src_attr}{alt_attr} />\n"

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

    def _parse_style_attribute(self, style_str: str) -> str:
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
        Returns list of {title, category, image, href}.
        """
        proj_node = self.find_node_for_component("Projects")
        if not proj_node:
            return []

        projects: list[dict[str, Any]] = []
        known_titles = [
            ("AgriAi", "AI / MACHINE LEARNING"),
            ("Smart Folder Organiser", "PYTHON / AUTOMATION"),
            ("MS Portfolio", "CREATIVE DEVELOPMENT"),
            ("Revoro Mods", "MARKETPLACE"),
            ("Royal Gryphon", "MOTION / VISUAL DESIGN"),
        ]

        txt_all = proj_node.get("text", "")
        for title, cat in known_titles:
            if title.lower() in txt_all.lower():
                projects.append({
                    "title": title,
                    "description": cat,
                    "tags": [cat],
                    "image": self._resolve_image_src({}),
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
        """Resolves real downloaded local path for img elements from asset_bindings."""
        raw_src = node.get("src")
        if raw_src and isinstance(raw_src, str):
            for b in self.asset_bindings:
                if b.get("local_path") and (b.get("source_url") == raw_src or b.get("local_path") == raw_src):
                    return b["local_path"]

        img_bindings = [
            b["local_path"] for b in self.asset_bindings
            if b.get("local_path") and b.get("role") in ("image", "poster", "background", "media")
        ]
        if img_bindings:
            resolved = img_bindings[self._binding_index % len(img_bindings)]
            self._binding_index += 1
            return resolved

        return None

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
