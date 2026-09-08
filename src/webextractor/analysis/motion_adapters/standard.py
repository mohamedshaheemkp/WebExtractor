from __future__ import annotations

import re
from typing import Any
from bs4 import BeautifulSoup
from .base import BaseMotionAdapter


class StandardCssMotionAdapter(BaseMotionAdapter):
    """
    Generic platform-agnostic motion adapter.
    Extracts CSS keyframes, CSS animation declarations, and standard data-motion/data-aos attributes.
    """

    def can_handle(self, html: str, css: str = "") -> bool:
        # Standard adapter runs universally on any website
        return True

    def extract_motion(self, html: str, css: str = "") -> dict[str, Any]:
        keyframes: list[dict[str, Any]] = []
        motion_triggers: list[dict[str, Any]] = []
        has_time_component = False

        # 1. Extract CSS keyframe animations
        if css:
            kf_matches = re.finditer(
                r"@keyframes\s+([a-zA-Z0-9_\-]+)\s*\{([^}]+)\}",
                css,
                re.IGNORECASE,
            )
            for m in kf_matches:
                keyframes.append({
                    "name": m.group(1),
                    "body": m.group(2).strip(),
                })

        # 2. Extract standard animation / aos attributes from HTML if present
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for el in soup.find_all(attrs={"data-aos": True}):
                effect = el.get("data-aos")
                delay = el.get("data-aos-delay", "0")
                duration = el.get("data-aos-duration", "800")
                classes = el.get("class", [])
                target = "." + ".".join(classes[:2]) if classes else el.name
                motion_triggers.append({
                    "trigger": "in_view",
                    "target": target,
                    "effect": effect,
                    "transition": {
                        "delay": float(delay) / 1000.0 if delay.isdigit() else 0.0,
                        "duration": float(duration) / 1000.0 if duration.isdigit() else 0.8,
                    },
                })

            # Check for standard dynamic time patterns (HH:MM:SS)
            for el in soup.find_all(True):
                txt = (el.get_text() or "").strip()
                if re.match(r"^\d{2}:\d{2}:\d{2}$", txt):
                    has_time_component = True
                    break

        return {
            "appear_animations": {},
            "keyframes": keyframes,
            "has_cursor": False,
            "has_time_component": has_time_component,
            "parallax_elements": [],
            "motion_triggers": motion_triggers,
        }
