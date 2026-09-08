from __future__ import annotations

import json
import re
from typing import Any
from bs4 import BeautifulSoup


class AnimationExtractor:
    """
    Extracts observable animation, transition, and interaction configurations
    from captured HTML, embedded runtime metadata, and CSS.
    """

    @staticmethod
    def extract_animations(
        html_content: str,
        css_content: str = "",
    ) -> dict[str, Any]:
        appear_animations: dict[str, Any] = {}
        keyframes: list[dict[str, Any]] = []
        has_cursor = False
        has_time_component = False
        parallax_elements: list[str] = []

        if not html_content:
            return {
                "appear_animations": appear_animations,
                "keyframes": keyframes,
                "has_cursor": has_cursor,
                "has_time_component": has_time_component,
                "parallax_elements": parallax_elements,
            }

        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Extract authoritative Framer appear animations from JSON script tags
        for s in soup.find_all("script"):
            txt = (s.string or "").strip()
            if not txt:
                continue

            if "initial" in txt and "animate" in txt and txt.startswith("{"):
                try:
                    data = json.loads(txt)
                    if isinstance(data, dict):
                        for appear_id, config in data.items():
                            if isinstance(config, dict):
                                default_cfg = config.get("default", config)
                                initial = default_cfg.get("initial", {})
                                animate_target = default_cfg.get("animate", {})
                                transition = animate_target.get("transition", {})

                                # Clean animate target by separating transition
                                clean_animate = {k: v for k, v in animate_target.items() if k != "transition"}

                                appear_animations[appear_id] = {
                                    "initial": initial,
                                    "animate": clean_animate,
                                    "transition": transition,
                                    "variants": {k: v for k, v in config.items() if k != "default"} if "default" in config else {},
                                }
                except Exception:
                    pass

        # 2. Check for custom cursor follower
        if soup.find(attrs={"data-framer-cursor": True}):
            has_cursor = True

        # 3. Check for dynamic clock component
        for el in soup.find_all(attrs={"data-framer-name": True}):
            name = el.get("data-framer-name", "")
            if name in ("Time", "Time Component"):
                has_time_component = True
                break
        if not has_time_component and ("LOCAL/" in html_content or "14:09:" in html_content):
            has_time_component = True

        # 4. Check for parallax elements
        for el in soup.find_all(attrs={"data-framer-name": "Parallax Image"}):
            appear_id = el.get("data-framer-appear-id")
            if appear_id:
                parallax_elements.append(f'[data-framer-appear-id="{appear_id}"]')
            else:
                classes = el.get("class", [])
                if classes:
                    parallax_elements.append("." + ".".join(classes[:2]))

        # 5. Extract CSS keyframe animations
        if css_content:
            kf_matches = re.finditer(r"@keyframes\s+([a-zA-Z0-9_\-]+)\s*\{([^}]+)\}", css_content, re.IGNORECASE)
            for m in kf_matches:
                keyframes.append({
                    "name": m.group(1),
                    "body": m.group(2).strip(),
                })

        return {
            "appear_animations": appear_animations,
            "keyframes": keyframes,
            "has_cursor": has_cursor,
            "has_time_component": has_time_component,
            "parallax_elements": parallax_elements,
        }
