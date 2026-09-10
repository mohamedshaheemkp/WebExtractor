from __future__ import annotations

import re
from typing import Any
from webextractor.model.interaction import (
    ActionSpec,
    Interaction,
    InteractionIR,
    TriggerSpec,
)


class InteractionAnalyzer:
    """
    Analyzes, normalizes, and classifies interaction patterns from
    observed browser behavioral probe evidence, CSS rules, and script signatures.
    Strictly decouples continuous visual motion from interaction state changes.
    """

    @classmethod
    def analyze_behavioral_interactions(
        cls,
        probe_interactions: list[dict[str, Any]] | None = None,
        html_content: str = "",
        css_content: str = "",
        js_content: str = "",
        routes: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        # 1. Process active behavioral probe observations
        if probe_interactions:
            for item in probe_interactions:
                if not isinstance(item, dict):
                    continue
                i_id = item.get("id") or f"interaction-{len(normalized) + 1:03d}"
                if i_id in seen_ids:
                    continue
                seen_ids.add(i_id)

                # Ensure structure complies with InteractionIR
                trigger_data = item.get("trigger", {})
                action_data = item.get("action", {})

                # Exclude developer/editor tooling generically
                sel_str = (trigger_data.get("selector") or "").lower()
                target_str = (action_data.get("target") or "").lower()
                if any(k in f"{sel_str} {target_str}" for k in ("__framer-editor", "__framer-badge", "editorbar", "webpack", "vite-overlay", "__react_devtools")):
                    continue

                # If this interaction revealed routes matching known routes, mark as menu navigation
                evidence = item.get("evidence", {})
                revealed_links = evidence.get("revealed_links", [])
                category = item.get("category", "generic")
                if revealed_links and category in ("generic", "menu"):
                    category = "menu"

                interaction = InteractionIR(
                    id=i_id,
                    category=category,
                    trigger=TriggerSpec(
                        type=trigger_data.get("type", "click"),
                        selector=trigger_data.get("selector", ""),
                        target_id=trigger_data.get("target_id"),
                        event_options=trigger_data.get("event_options", {}),
                    ),
                    action=ActionSpec(
                        type=action_data.get("type", "toggle"),
                        target=action_data.get("target"),
                        target_route=action_data.get("target_route"),
                        transition=action_data.get("transition", {"duration": 0.3, "easing": "ease-in-out"}),
                    ),
                    states=item.get("states", {}),
                    animation=item.get("animation", {}),
                    conditions=item.get("conditions", {}),
                    evidence=evidence,
                    description=item.get("description", f"Behavioral {category} interaction"),
                )
                normalized.append(interaction.to_dict())

        # 2. Extract Route Transition evidence from HTML/JS/CSS if present
        route_transition = cls._detect_route_transitions(html_content, css_content, js_content)
        if route_transition and not any(i.get("category") == "route_transition" for i in normalized):
            normalized.append(route_transition.to_dict())

        # 3. Extract Cursor Follower behavior from evidence if present
        cursor_interaction = cls._detect_cursor_interaction(html_content, css_content)
        if cursor_interaction and not any(i.get("category") == "cursor" for i in normalized):
            normalized.append(cursor_interaction.to_dict())

        return normalized

    @classmethod
    def _detect_route_transitions(
        cls,
        html_content: str,
        css_content: str = "",
        js_content: str = "",
    ) -> InteractionIR | None:
        """Detects whether route navigation uses animated page transitions."""
        has_transition = False
        transition_type = "fade"
        duration = 0.4

        if "route-transition" in css_content.lower() or "page-transition" in css_content.lower() or "view-transition" in css_content.lower():
            has_transition = True
            if "wipe" in css_content.lower():
                transition_type = "wipe"
            elif "slide" in css_content.lower():
                transition_type = "slide"

        if has_transition:
            return InteractionIR(
                id="interaction-route-transition",
                category="route_transition",
                trigger=TriggerSpec(
                    type="click",
                    selector='a[href^="/"]',
                ),
                action=ActionSpec(
                    type="navigate",
                    transition={"type": transition_type, "duration": duration},
                ),
                description=f"Route exit/enter transition ({transition_type})",
            )
        return None

    @classmethod
    def _detect_cursor_interaction(
        cls,
        html_content: str,
        css_content: str = "",
    ) -> InteractionIR | None:
        """Detects custom cursor interactions on hoverable targets."""
        has_custom_cursor = "data-framer-cursor" in html_content or "custom-cursor" in css_content.lower() or "cursor-follower" in css_content.lower()
        if has_custom_cursor:
            return InteractionIR(
                id="interaction-cursor-hover",
                category="cursor",
                trigger=TriggerSpec(
                    type="hover",
                    selector="a, button, [role='button'], .project-card, [data-cursor]",
                ),
                action=ActionSpec(
                    type="state_change",
                    target="#custom-cursor",
                    transition={"duration": 0.15, "easing": "ease-out"},
                ),
                states={
                    "default": {"scale": 1, "opacity": 1},
                    "hover": {"scale": 2.2, "opacity": 0.9, "text": "VIEW"},
                },
                description="Custom cursor follower with hover scaling",
            )
        return None

    @staticmethod
    def analyze_interactions(css_content: str, js_content: str = "") -> list[Interaction]:
        """
        Legacy backwards-compatible method returning simple Interaction objects.
        Preserves compatibility with existing test suites.
        """
        interactions = []

        # Keyframe animations in CSS
        keyframes = re.findall(r"@keyframes\s+([a-zA-Z0-9_-]+)", css_content)
        for kf in set(keyframes):
            interactions.append(
                Interaction(
                    trigger="load",
                    selector="body",
                    action="animate",
                    animation_details={"keyframe": kf},
                    description=f"CSS keyframe animation: {kf}",
                )
            )

        # GSAP / Framer Motion / Lenis detection in JS
        if "gsap" in js_content.lower():
            interactions.append(
                Interaction(
                    trigger="scroll",
                    selector="[data-scroll]",
                    action="gsap_scroll_trigger",
                    description="GSAP ScrollTrigger detected",
                )
            )

        if "framer-motion" in js_content.lower() or "framer" in js_content.lower():
            interactions.append(
                Interaction(
                    trigger="hover",
                    selector=".framer-interactive",
                    action="framer_motion",
                    description="Framer Motion component animations",
                )
            )

        return interactions
