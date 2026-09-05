from __future__ import annotations

import re
from webextractor.model.interaction import Interaction


class InteractionAnalyzer:
    """Analyzes interaction and animation patterns in CSS and JavaScript."""

    @staticmethod
    def analyze_interactions(css_content: str, js_content: str = "") -> list[Interaction]:
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
