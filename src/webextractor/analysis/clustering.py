from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClusteredComponent:
    name: str
    inferred_type: str
    occurrences: int
    confidence: float
    sample_text: str
    classes: list[str] = field(default_factory=list)
    child_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "inferred_type": self.inferred_type,
            "occurrences": self.occurrences,
            "confidence": round(self.confidence, 2),
            "sample_text": self.sample_text,
            "classes": self.classes,
            "child_tags": self.child_tags,
        }


class ComponentClusterer:
    """
    Filters raw DOM repetition signatures, discards trivial layout wrappers,
    and clusters high-value repeating UI patterns into named reusable components.
    """

    NAME_PATTERNS = [
        (r"(project|work|portfolio|repo|app)", "ProjectCard"),
        (r"(capabil|service|feature|offering)", "CapabilityItem"),
        (r"(journey|timeline|experience|education|history)", "JourneyItem"),
        (r"(tool|stack|skill|tech|language)", "ToolkitItem"),
        (r"(testimonial|review|feedback)", "TestimonialCard"),
        (r"(faq|question|answer|accordion)", "AccordionItem"),
        (r"(nav|menu|link|item)", "NavItem"),
        (r"(card|post|article|item)", "Card"),
    ]

    def cluster(
        self,
        repeated_groups: dict[str, Any],
        component_tree: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        clusters: list[ClusteredComponent] = []

        for signature, group in repeated_groups.items():
            count = group.get("count", 0)
            nodes = group.get("nodes", [])
            if count < 2 or not nodes:
                continue

            first_node = nodes[0]
            tag = first_node.get("tag", "div")
            classes = first_node.get("classes", [])
            text = " ".join(n.get("text", "") for n in nodes).strip()
            first_text = first_node.get("text", "").strip()

            # Skip trivial layout wrappers (empty divs or generic single-span containers)
            if not text and not classes:
                continue
            if tag in ("br", "hr", "path", "svg", "use", "foreignobject", "script", "style"):
                continue

            # Calculate Component Quality Score
            score = self._score_component(tag, classes, nodes, text)
            if score < 0.60:
                continue

            # Infer Component Name
            name = self._infer_name(classes, text, tag)

            clusters.append(
                ClusteredComponent(
                    name=name,
                    inferred_type=tag,
                    occurrences=count,
                    confidence=min(0.99, score),
                    sample_text=first_text[:80],
                    classes=classes[:3],
                    child_tags=first_node.get("child_tags", []),
                )
            )

        # Deduplicate & sort by confidence and occurrences
        unique_clusters: dict[str, ClusteredComponent] = {}
        for c in sorted(clusters, key=lambda x: (x.confidence, x.occurrences), reverse=True):
            if c.name not in unique_clusters:
                unique_clusters[c.name] = c

        return [c.to_dict() for c in unique_clusters.values()]

    def _score_component(
        self,
        tag: str,
        classes: list[str],
        nodes: list[dict[str, Any]],
        text: str,
    ) -> float:
        score = 0.50

        # Substantial text presence across items
        if len(text) > 40:
            score += 0.20

        # Meaningful CSS class identifiers
        class_str = " ".join(classes).lower()
        if any(w in class_str for w in ("card", "item", "row", "col", "box", "block", "project", "skill")):
            score += 0.20

        # Reasonable repetition count (2 to 30 is typical for UI cards/lists)
        if 2 <= len(nodes) <= 20:
            score += 0.15
        elif len(nodes) > 40:
            # Over-frequent might be tiny inline wrappers
            score -= 0.15

        return score

    def _infer_name(
        self,
        classes: list[str],
        text: str,
        tag: str,
    ) -> str:
        combined = f"{' '.join(classes)} {text}".lower()

        for pattern, name in self.NAME_PATTERNS:
            if re.search(pattern, combined):
                return name

        if tag in ("li", "article"):
            return "ListItem"

        return "CardItem"
