from __future__ import annotations

from typing import Any
from bs4 import BeautifulSoup

from webextractor.model.component import ComponentNode


class DOMExtractor:
    """Extracts semantic tree, computed styles, and element hierarchy from DOM."""

    @staticmethod
    async def extract_from_page(page: Any) -> list[ComponentNode]:
        """Extract structured component hierarchy using browser execution."""
        js_script = """
        () => {
            function getStyles(el) {
                const cs = window.getComputedStyle(el);
                return {
                    color: cs.color,
                    backgroundColor: cs.backgroundColor,
                    fontSize: cs.fontSize,
                    fontWeight: cs.fontWeight,
                    fontFamily: cs.fontFamily,
                    display: cs.display,
                    flexDirection: cs.flexDirection,
                    borderRadius: cs.borderRadius,
                    padding: cs.padding,
                    margin: cs.margin
                };
            }

            function parseNode(el, depth = 0) {
                if (depth > 6) return null;
                const tag = el.tagName ? el.tagName.toLowerCase() : '';
                if (['script', 'style', 'noscript', 'meta', 'link', 'svg'].includes(tag)) return null;

                const text = Array.from(el.childNodes)
                    .filter(n => n.nodeType === 3)
                    .map(n => n.textContent.trim())
                    .filter(Boolean)
                    .join(' ');

                const children = Array.from(el.children)
                    .map(c => parseNode(c, depth + 1))
                    .filter(Boolean);

                return {
                    tag: tag,
                    className: el.className || '',
                    id: el.id || '',
                    text: text,
                    styles: getStyles(el),
                    children: children
                };
            }

            const body = document.body;
            return body ? Array.from(body.children).map(c => parseNode(c, 0)).filter(Boolean) : [];
        }
        """
        raw_nodes = await page.evaluate(js_script)
        components = []

        def build_node(raw: dict[str, Any], idx: int) -> ComponentNode:
            tag = raw.get("tag", "div")
            cls = raw.get("className", "")
            if not isinstance(cls, str):
                cls = ""
            name = f"{tag.capitalize()}_{idx}"
            if "hero" in cls.lower():
                name = "Hero"
            elif "nav" in tag or "nav" in cls.lower() or "header" in tag:
                name = "Navbar"
            elif "footer" in tag or "footer" in cls.lower():
                name = "Footer"
            elif "project" in cls.lower():
                name = "Projects"
            elif "about" in cls.lower():
                name = "About"
            elif "contact" in cls.lower():
                name = "Contact"

            child_nodes = [build_node(c, i) for i, c in enumerate(raw.get("children", []))]
            return ComponentNode(
                name=name,
                tag_name=tag,
                text_content=raw.get("text", ""),
                styles=raw.get("styles", {}),
                children=child_nodes,
            )

        for i, raw in enumerate(raw_nodes):
            components.append(build_node(raw, i))

        return components

    @staticmethod
    def extract_from_html(html_content: str) -> list[ComponentNode]:
        """Extract component hierarchy from static HTML."""
        soup = BeautifulSoup(html_content, "lxml")
        body = soup.find("body") or soup
        components = []

        sections = body.find_all(["header", "nav", "section", "main", "footer", "article", "div"], recursive=False)
        if not sections:
            sections = body.find_all(["section", "div"], limit=10)

        for idx, sec in enumerate(sections):
            tag = sec.name
            cls = " ".join(sec.get("class", [])) if isinstance(sec.get("class"), list) else sec.get("class", "")
            name = f"Section_{idx + 1}"
            cat = "section"

            if "nav" in tag or "nav" in cls.lower() or "header" in tag:
                name = "Navbar"
                cat = "navbar"
            elif "footer" in tag or "footer" in cls.lower():
                name = "Footer"
                cat = "footer"
            elif "hero" in cls.lower() or idx == 0:
                name = "Hero"
                cat = "hero"
            elif "project" in cls.lower():
                name = "Projects"
                cat = "card"
            elif "about" in cls.lower():
                name = "About"
                cat = "section"

            text = " ".join(sec.stripped_strings)
            components.append(
                ComponentNode(
                    name=name,
                    category=cat,
                    tag_name=tag,
                    text_content=text[:200],
                )
            )

        return components
