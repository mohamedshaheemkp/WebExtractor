from __future__ import annotations

import json
import re
from typing import Any
from bs4 import BeautifulSoup
from .base import BaseMotionAdapter


class FramerMotionAdapter(BaseMotionAdapter):
    """
    Source-specific adapter for Framer websites.
    Extracts appear animations from Framer's hydration scripts, spring parameters,
    custom cursor tags, and parallax elements.
    """

    def can_handle(self, html: str, css: str = "") -> bool:
        if not html:
            return False
        return (
            "framer" in html.lower()
            or "data-framer-" in html
            or 'type="framer/appear"' in html
        )

    def extract_motion(self, html: str, css: str = "") -> dict[str, Any]:
        appear_animations: dict[str, Any] = {}
        has_cursor = False
        has_time_component = False
        parallax_elements: list[str] = []
        motion_triggers: list[dict[str, Any]] = []

        if not html:
            return {
                "appear_animations": appear_animations,
                "keyframes": [],
                "has_cursor": has_cursor,
                "has_time_component": has_time_component,
                "parallax_elements": parallax_elements,
                "motion_triggers": motion_triggers,
            }

        soup = BeautifulSoup(html, "html.parser")

        # 1. Extract Framer appear animations from JSON script tags
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

                                if isinstance(transition, dict):
                                    ease_val = (
                                        transition.get("ease")
                                        or transition.get("easing")
                                        or transition.get("timing_function")
                                    )
                                    if isinstance(ease_val, list) and len(ease_val) == 4:
                                        tf = f"cubic-bezier({ease_val[0]}, {ease_val[1]}, {ease_val[2]}, {ease_val[3]})"
                                        transition["timing_function"] = tf
                                        transition["easing"] = tf
                                        transition["ease"] = tf
                                    elif isinstance(ease_val, str) and ease_val:
                                        transition["timing_function"] = ease_val
                                        transition["easing"] = ease_val
                                        transition["ease"] = ease_val
                                    elif "timing_function" in transition and isinstance(transition["timing_function"], str):
                                        tf = transition["timing_function"]
                                        transition["easing"] = tf
                                        transition["ease"] = tf

                                    if "duration" in transition:
                                        try:
                                            transition["duration"] = float(transition["duration"])
                                        except (ValueError, TypeError):
                                            pass

                                clean_animate = {
                                    k: v for k, v in animate_target.items() if k != "transition"
                                }

                                variants = (
                                    {k: v for k, v in config.items() if k != "default"}
                                    if "default" in config
                                    else {}
                                )

                                appear_animations[appear_id] = {
                                    "initial": initial,
                                    "animate": clean_animate,
                                    "transition": transition,
                                    "variants": variants,
                                }

                                motion_triggers.append({
                                    "trigger": "mount",
                                    "target": f'[data-framer-appear-id="{appear_id}"]',
                                    "id": appear_id,
                                    "initial": initial,
                                    "animate": clean_animate,
                                    "transition": transition,
                                    "variants": variants,
                                })
                except Exception:
                    pass

        # 1b. Fallback: extract from elements with data-framer-appear-id if not in scripts
        for el in soup.find_all(attrs={"data-framer-appear-id": True}):
            appear_id = el.get("data-framer-appear-id")
            if appear_id and appear_id not in appear_animations:
                style = el.get("style", "")
                initial_cfg: dict[str, Any] = {"opacity": 0}
                if "opacity:" in style:
                    op_m = re.search(r"opacity\s*:\s*([0-9.]+)", style)
                    if op_m:
                        try:
                            op_val = float(op_m.group(1))
                            initial_cfg["opacity"] = 0 if op_val <= 0.05 else op_val
                        except ValueError:
                            pass
                if "translate" in style:
                    y_m = re.search(r"translate[Y3d]*\([^)]*?(-?[0-9.]+)px", style)
                    if y_m:
                        try:
                            initial_cfg["y"] = float(y_m.group(1))
                        except ValueError:
                            pass

                trans_cfg: dict[str, Any] = {"type": "spring", "stiffness": 200, "damping": 40}
                if "transition" in style:
                    dur_m = re.search(r"(?:^|[^\w.])([0-9]*\.?[0-9]+)(m?s)(?=[^\w]|$)", style)
                    if dur_m:
                        v = float(dur_m.group(1))
                        trans_cfg["duration"] = v / 1000.0 if dur_m.group(2) == "ms" else v
                    tf_m = re.search(
                        r"(cubic-bezier\([^)]+\)|steps\([^)]+\)|step-start|step-end|ease-in-out|ease-in|ease-out|linear|ease)",
                        style,
                        re.IGNORECASE,
                    )
                    if tf_m:
                        tf_str = tf_m.group(0).strip()
                        trans_cfg["timing_function"] = tf_str
                        trans_cfg["easing"] = tf_str
                        trans_cfg["ease"] = tf_str

                appear_animations[appear_id] = {
                    "initial": initial_cfg,
                    "animate": {"opacity": 1, "y": 0},
                    "transition": trans_cfg,
                    "variants": {},
                }
                motion_triggers.append({
                    "trigger": "mount",
                    "target": f'[data-framer-appear-id="{appear_id}"]',
                    "id": appear_id,
                    "initial": initial_cfg,
                    "animate": {"opacity": 1, "y": 0},
                    "transition": trans_cfg,
                    "variants": {},
                })

        # 2. Extract Framer cursor elements
        if soup.find(attrs={"data-framer-cursor": True}):
            has_cursor = True

        # 3. Dynamic clock component
        for el in soup.find_all(attrs={"data-framer-name": True}):
            name = el.get("data-framer-name", "")
            if name in ("Time", "Time Component"):
                has_time_component = True
                break
        if not has_time_component:
            for el in soup.find_all(True):
                txt = (el.get_text() or "").strip()
                if re.match(r"^\d{2}:\d{2}:\d{2}$", txt):
                    has_time_component = True
                    break

        # 4. Parallax elements
        for el in soup.find_all(attrs={"data-framer-name": "Parallax Image"}):
            appear_id = el.get("data-framer-appear-id")
            if appear_id:
                parallax_elements.append(f'[data-framer-appear-id="{appear_id}"]')
            else:
                classes = el.get("class", [])
                if classes:
                    parallax_elements.append("." + ".".join(classes[:2]))

        return {
            "appear_animations": appear_animations,
            "keyframes": [],
            "has_cursor": has_cursor,
            "has_time_component": has_time_component,
            "parallax_elements": parallax_elements,
            "motion_triggers": motion_triggers,
        }
