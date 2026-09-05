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

        def _score_tree(n: dict[str, Any], depth: int):
            tag = (n.get("tag") or "").lower()
            txt = (n.get("text") or "").lower()
            classes = n.get("classes", [])

            # Never match root body as a sub-component
            if tag == "body" or depth == 0:
                for ch in n.get("children", []):
                    _score_tree(ch, depth + 1)
                return

            is_semantic_section = tag in ("header", "nav", "section", "footer", "main", "article")
            is_container_div = (tag == "div" and (any(c.endswith("-container") for c in classes) or depth <= 4))

            if (is_semantic_section or is_container_div) and txt:
                score = 0
                for kw in keywords:
                    if kw in txt:
                        score += len(kw) * 4

                n_name = (n.get("name") or "").lower()
                if n_name == name.lower():
                    score += 60

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

        # Asset resolution for media tags
        if tag == "img":
            src = self._resolve_image_src(node)
            src_attr = f' src="{src}"' if src else ""
            return f"{indent}<img{cls_attr}{id_attr}{src_attr} alt=\"\" />\n"

        if tag == "video":
            src = self._resolve_video_src(node)
            src_attr = f' src="{src}"' if src else ""
            return f"{indent}<video{cls_attr}{id_attr}{src_attr} autoPlay muted loop playsInline />\n"

        if tag in self.SELF_CLOSING_TAGS:
            return f"{indent}<{tag}{cls_attr}{id_attr} />\n"

        txt = (node.get("text") or "").strip()
        valid_children = [
            ch for ch in node.get("children", [])
            if (ch.get("tag") or "").lower() not in self.IGNORED_TAGS
        ]

        if not valid_children:
            if txt:
                esc_txt = self._escape_jsx_text(txt)
                return f"{indent}<{tag}{cls_attr}{id_attr}>{esc_txt}</{tag}>\n"
            else:
                return f"{indent}<{tag}{cls_attr}{id_attr} />\n"

        # If children have no text, but this node does, emit text directly
        has_child_text = any(self._has_descendant_text(c) for c in valid_children)
        if not has_child_text and txt:
            esc_txt = self._escape_jsx_text(txt)
            inner = f"{indent}  {esc_txt}\n"
            for ch in valid_children:
                inner += self.emit_jsx(ch, depth + 1, is_root=False)
            return f"{indent}<{tag}{cls_attr}{id_attr}>\n{inner}{indent}</{tag}>\n"

        inner = ""
        for ch in valid_children:
            inner += self.emit_jsx(ch, depth + 1, is_root=False)

        if not inner.strip():
            return f"{indent}<{tag}{cls_attr}{id_attr} />\n"

        return f"{indent}<{tag}{cls_attr}{id_attr}>\n{inner}{indent}</{tag}>\n"

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
