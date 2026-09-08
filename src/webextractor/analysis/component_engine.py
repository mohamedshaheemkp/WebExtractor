from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComponentNode:
    name: str
    tag: str
    role: str | None = None
    text: str = ""
    classes: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    styles: dict[str, str] = field(default_factory=dict)
    children: list["ComponentNode"] = field(
        default_factory=list
    )
    repeated: bool = False
    repeat_count: int = 1
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tag": self.tag,
            "role": self.role,
            "text": self.text,
            "classes": self.classes,
            "attributes": self.attributes,
            "styles": self.styles,
            "children": [
                child.to_dict()
                for child in self.children
            ],
            "repeated": self.repeated,
            "repeat_count": self.repeat_count,
            "confidence": self.confidence,
        }


class ComponentEngine:
    """
    Converts the captured DOM into a semantic component tree.

    This intentionally uses observable structure rather than
    pretending to recover the original source components.
    """

    SEMANTIC_NAMES = {
        "header": "Header",
        "nav": "Navigation",
        "main": "Main",
        "footer": "Footer",
        "article": "Article",
        "aside": "Sidebar",
        "form": "Form",
        "button": "Button",
        "img": "Image",
        "video": "Video",
        "ul": "List",
        "ol": "List",
    }

    SECTION_HINTS = {
        "hero": "Hero",
        "intro": "Intro",
        "about": "About",
        "project": "Projects",
        "work": "Work",
        "capabil": "Capabilities",
        "service": "Services",
        "skill": "Skills",
        "tool": "Toolkit",
        "journey": "Journey",
        "experience": "Experience",
        "education": "Education",
        "contact": "Contact",
        "footer": "Footer",
        "voice": "Voice",
        "testimonial": "Testimonials",
        "faq": "FAQ",
    }

    def analyze(
        self,
        dom_tree: dict[str, Any],
    ) -> ComponentNode:

        return self._build(
            dom_tree,
            depth=0,
        )

    def _build(
        self,
        node: dict[str, Any],
        depth: int,
    ) -> ComponentNode:

        tag = (
            node.get("tag")
            or "div"
        )

        classes = node.get(
            "classes",
            [],
        ) or []

        element_id = node.get(
            "id"
        )

        text = node.get(
            "text",
            "",
        ) or ""

        role = node.get(
            "role"
        )

        name, confidence = (
            self._infer_name(
                tag=tag,
                element_id=element_id,
                classes=classes,
                text=text,
                role=role,
            )
        )

        children = []

        if depth < 20:

            for child in node.get(
                "children",
                [],
            ):

                child_component = (
                    self._build(
                        child,
                        depth + 1,
                    )
                )

                children.append(
                    child_component
                )

        attributes = dict(node.get("attributes") or {})
        styles = dict(node.get("styles") or {})
        for attr_k in ("viewBox", "width", "height", "transform", "preserveAspectRatio", "clipPath", "src", "poster", "href", "target", "alt"):
            if node.get(attr_k) and attr_k not in attributes:
                attributes[attr_k] = str(node[attr_k])
        if element_id and "id" not in attributes:
            attributes["id"] = element_id

        return ComponentNode(
            name=name,
            tag=tag,
            role=role,
            text=text[:500],
            classes=classes,
            attributes=attributes,
            styles=styles,
            children=children,
            confidence=confidence,
        )

    def _infer_name(
        self,
        tag: str,
        element_id: str | None,
        classes: list[str],
        text: str,
        role: str | None,
    ) -> tuple[str, float]:

        # 1. Accessibility role.
        if role:
            role_name = self._role_to_name(
                role
            )

            if role_name:
                return role_name, 0.95

        # 2. Semantic HTML.
        if tag in self.SEMANTIC_NAMES:
            return (
                self.SEMANTIC_NAMES[tag],
                0.95,
            )

        # 3. ID / class hints.
        identifiers = []

        if element_id:
            identifiers.append(
                element_id
            )

        identifiers.extend(classes)

        identifier_text = " ".join(
            identifiers
        ).lower()

        for hint, component_name in (
            self.SECTION_HINTS.items()
        ):

            if hint in identifier_text:
                return (
                    component_name,
                    0.85,
                )

        # 4. Text hints.
        text_lower = text.lower()

        for hint, component_name in (
            self.SECTION_HINTS.items()
        ):

            if hint in text_lower[:300]:
                return (
                    component_name,
                    0.65,
                )

        # 5. Generic fallback.
        return (
            self._generic_name(tag),
            0.40,
        )

    @staticmethod
    def _role_to_name(
        role: str,
    ) -> str | None:

        roles = {
            "banner": "Header",
            "navigation": "Navigation",
            "main": "Main",
            "contentinfo": "Footer",
            "button": "Button",
            "dialog": "Dialog",
            "list": "List",
            "listitem": "ListItem",
            "article": "Article",
            "complementary": "Sidebar",
            "form": "Form",
        }

        return roles.get(
            role.lower()
        )

    @staticmethod
    def _generic_name(
        tag: str,
    ) -> str:

        if not tag:
            return "Component"

        return (
            tag.capitalize()
        )
