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
        default_duration = 0.6
        default_easing: str | None = None

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

            # Derive realistic default reveal duration and timing function from
            # the site's own transition declarations.
            trans_matches = re.findall(
                r"transition(?:-[a-z-]+)?\s*:\s*([^;]+);?",
                css,
                re.IGNORECASE,
            )
            extracted_durations: list[float] = []
            extracted_easings: list[str] = []

            for tm in trans_matches:
                tm_str = tm.strip()
                # 1. Parse duration in s or ms (supporting leading decimals like .3s as well as 1.2s)
                d_m = re.search(r"(?:^|[^\d.])(\d*\.?\d+)(m?s)(?:[^\w]|$)", tm_str)
                if d_m:
                    try:
                        val = float(d_m.group(1))
                        if d_m.group(2) == "ms":
                            val /= 1000.0
                        if val > 0:
                            extracted_durations.append(val)
                    except ValueError:
                        pass

                # 2. Parse timing function (cubic-bezier, steps, or standard keywords)
                tf_m = re.search(
                    r"(cubic-bezier\([^)]+\)|steps\([^)]+\)|linear|ease-in-out|ease-in|ease-out|ease)",
                    tm_str,
                    re.IGNORECASE,
                )
                if tf_m:
                    tf_val = tf_m.group(1).strip()
                    extracted_easings.append(tf_val)

            if extracted_durations:
                default_duration = sum(extracted_durations) / len(extracted_durations)

            # Prioritize specific easing curves (cubic-bezier/steps > named non-ease curves > ease)
            default_easing: str | None = None
            for e in extracted_easings:
                if "cubic-bezier" in e.lower() or "steps" in e.lower():
                    default_easing = e
                    break
            if not default_easing:
                for e in extracted_easings:
                    if e.lower() not in ("ease", "linear"):
                        default_easing = e
                        break
            if not default_easing and extracted_easings:
                default_easing = extracted_easings[0]

            # Also parse rules with selectors to bind transitions directly
            element_transitions: dict[str, dict[str, Any]] = {}
            rule_matches = re.finditer(r"([^{}]+)\{([^}]+)\}", css)
            for rm in rule_matches:
                sel = rm.group(1).strip()
                body = rm.group(2).strip()
                if "transition" in body:
                    tm = re.search(r"transition(?:-[a-z-]+)?\s*:\s*([^;]+);?", body, re.IGNORECASE)
                    if tm:
                        t_str = tm.group(1).strip()
                        dur_val = None
                        d_m = re.search(r"(?:^|[^\d.])(\d*\.?\d+)(m?s)(?:[^\w]|$)", t_str)
                        if d_m:
                            try:
                                v = float(d_m.group(1))
                                dur_val = v / 1000.0 if d_m.group(2) == "ms" else v
                            except ValueError:
                                pass
                        tf_m = re.search(
                            r"(cubic-bezier\([^)]+\)|steps\([^)]+\)|linear|ease-in-out|ease-in|ease-out|ease)",
                            t_str,
                            re.IGNORECASE,
                        )
                        tf_val = tf_m.group(1).strip() if tf_m else None
                        if dur_val or tf_val:
                            clean_sel = sel.split(",")[0].strip()
                            resolved_tf = tf_val or default_easing
                            element_transitions[clean_sel] = {
                                "duration": dur_val or default_duration,
                                "type": "tween",
                                "timing_function": resolved_tf,
                                "easing": resolved_tf,
                                "ease": resolved_tf,
                                "raw": t_str,
                            }
        else:
            element_transitions = {}

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
                        "timing_function": default_easing,
                        "easing": default_easing,
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
            "element_transitions": element_transitions,
            "default_transition_duration": default_duration,
            "default_timing_function": default_easing,
            "default_easing": default_easing,
            "timing_function": default_easing,
        }
