from __future__ import annotations

from typing import Any
from .motion_adapters.base import BaseMotionAdapter
from .motion_adapters.framer import FramerMotionAdapter
from .motion_adapters.standard import StandardCssMotionAdapter


class AnimationExtractor:
    """
    Coordinates platform-specific motion adapters to extract and normalize
    animation and interaction metadata from captured websites.
    """

    def __init__(self, adapters: list[BaseMotionAdapter] | None = None):
        if adapters is None:
            self.adapters = [
                FramerMotionAdapter(),
                StandardCssMotionAdapter(),
            ]
        else:
            self.adapters = adapters

    def analyze_motion(
        self,
        html_content: str,
        css_content: str = "",
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "appear_animations": {},
            "element_transitions": {},
            "keyframes": [],
            "has_cursor": False,
            "has_time_component": False,
            "parallax_elements": [],
            "motion_triggers": [],
            "default_transition_duration": 0.6,
            "default_timing_function": None,
            "default_easing": None,
            "timing_function": None,
        }

        for adapter in self.adapters:
            if adapter.can_handle(html_content, css_content):
                res = adapter.extract_motion(html_content, css_content)
                merged["appear_animations"].update(res.get("appear_animations", {}))
                if res.get("element_transitions"):
                    merged["element_transitions"].update(res["element_transitions"])
                merged["keyframes"].extend(res.get("keyframes", []))
                if res.get("has_cursor"):
                    merged["has_cursor"] = True
                if res.get("has_time_component"):
                    merged["has_time_component"] = True
                merged["parallax_elements"].extend(res.get("parallax_elements", []))
                merged["motion_triggers"].extend(res.get("motion_triggers", []))
                if res.get("default_transition_duration"):
                    merged["default_transition_duration"] = res["default_transition_duration"]
                tf_val = res.get("default_timing_function") or res.get("default_easing") or res.get("timing_function")
                if tf_val:
                    merged["default_timing_function"] = tf_val
                    merged["default_easing"] = tf_val
                    merged["timing_function"] = tf_val

        # Deduplicate list elements preserving order
        merged["parallax_elements"] = list(dict.fromkeys(merged["parallax_elements"]))
        merged["keyframes"] = [
            dict(t) for t in {tuple(sorted(d.items())) for d in merged["keyframes"]}
        ]

        return merged

    @classmethod
    def extract_animations(
        cls,
        html_content: str,
        css_content: str = "",
    ) -> dict[str, Any]:
        """Backwards-compatible classmethod matching legacy signature."""
        instance = cls()
        return instance.analyze_motion(html_content, css_content)
