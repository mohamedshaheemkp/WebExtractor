from __future__ import annotations

import re
from typing import Any
from bs4 import BeautifulSoup
from .base import BaseMotionAdapter


TIMING_FUNCTION_RE = re.compile(
    r"(cubic-bezier\([^)]+\)|steps\([^)]+\)|step-start|step-end|ease-in-out|ease-in|ease-out|linear|ease)",
    re.IGNORECASE,
)
TIME_TOKEN_RE = re.compile(
    r"(?<![\w.])([0-9]*\.?[0-9]+)(m?s)(?![\w])",
    re.IGNORECASE,
)


class StandardCssMotionAdapter(BaseMotionAdapter):
    """
    Generic platform-agnostic motion adapter.
    Extracts CSS keyframes, CSS animation declarations, and standard data-motion/data-aos attributes.
    """

    def can_handle(self, html: str, css: str = "") -> bool:
        if not html and not css:
            return False
        has_css = bool(
            css
            and (
                "@keyframes" in css
                or "transition" in css
                or "animation" in css
            )
        )
        has_html = bool(
            html
            and (
                "data-aos" in html
                or "data-motion" in html
                or re.search(r"\b\d{2}:\d{2}:\d{2}\b", html)
            )
        )
        return has_css or has_html

    @staticmethod
    def _parse_transition_clause(clause: str) -> tuple[float | None, str | None, float | None]:
        """
        Parses a single transition clause according to CSS specs:
        transition: [property] [duration] [timing-function] [delay]
        Returns (duration, timing_function, delay).
        Correctly handles: .3s, 0.3s, 1.2s, 0s without confusing duration with delay.
        """
        tf_match = TIMING_FUNCTION_RE.search(clause)
        tf_val = tf_match.group(0).strip() if tf_match else None

        # Strip timing function so unitless numbers inside cubic-bezier/steps aren't matched as times
        clause_no_tf = TIMING_FUNCTION_RE.sub("", clause)
        times = list(TIME_TOKEN_RE.finditer(clause_no_tf))

        dur_val: float | None = None
        delay_val: float | None = None

        if len(times) >= 1:
            v = float(times[0].group(1))
            dur_val = v / 1000.0 if times[0].group(2).lower() == "ms" else v
        if len(times) >= 2:
            v = float(times[1].group(1))
            delay_val = v / 1000.0 if times[1].group(2).lower() == "ms" else v

        return dur_val, tf_val, delay_val

    def extract_motion(
        self, html: str, css: str = "", claimed_targets: set[str] | None = None
    ) -> dict[str, Any]:
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
            extracted_durations: list[float] = []
            extracted_easings: list[str] = []

            # 1a. Explicit transition-duration properties
            for dur_m in re.finditer(r"transition-duration\s*:\s*([^;]+)", css, re.IGNORECASE):
                for tm in TIME_TOKEN_RE.finditer(dur_m.group(1)):
                    v = float(tm.group(1))
                    val = v / 1000.0 if tm.group(2).lower() == "ms" else v
                    if val > 0:
                        extracted_durations.append(val)

            # 1b. Explicit transition-timing-function properties
            for tf_m in re.finditer(r"transition-timing-function\s*:\s*([^;]+)", css, re.IGNORECASE):
                for match in TIMING_FUNCTION_RE.finditer(tf_m.group(1)):
                    extracted_easings.append(match.group(0).strip())

            # 1c. Shorthand transition declarations
            for sh_m in re.finditer(r"(?<![a-zA-Z0-9_-])transition\s*:\s*([^;]+);?", css, re.IGNORECASE):
                parts = re.split(r",\s*(?![^(]*\))", sh_m.group(1).strip())
                for part in parts:
                    d_val, t_val, _ = self._parse_transition_clause(part)
                    if d_val is not None and d_val > 0:
                        extracted_durations.append(d_val)
                    if t_val:
                        extracted_easings.append(t_val)

            if extracted_durations:
                default_duration = sum(extracted_durations) / len(extracted_durations)

            # Prioritize specific easing curves (cubic-bezier/steps > named non-ease curves > ease/linear)
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
                    dur_val: float | None = None
                    tf_val: str | None = None
                    delay_val: float | None = None
                    raw_str: str = ""

                    # Check longhands first
                    dur_match = re.search(r"transition-duration\s*:\s*([^;]+)", body, re.IGNORECASE)
                    if dur_match:
                        raw_str = dur_match.group(0)
                        times = list(TIME_TOKEN_RE.finditer(dur_match.group(1)))
                        if times:
                            v = float(times[0].group(1))
                            dur_val = v / 1000.0 if times[0].group(2).lower() == "ms" else v

                    tf_match = re.search(r"transition-timing-function\s*:\s*([^;]+)", body, re.IGNORECASE)
                    if tf_match:
                        raw_str = raw_str or tf_match.group(0)
                        m = TIMING_FUNCTION_RE.search(tf_match.group(1))
                        if m:
                            tf_val = m.group(0).strip()

                    delay_match = re.search(r"transition-delay\s*:\s*([^;]+)", body, re.IGNORECASE)
                    if delay_match:
                        times = list(TIME_TOKEN_RE.finditer(delay_match.group(1)))
                        if times:
                            v = float(times[0].group(1))
                            delay_val = v / 1000.0 if times[0].group(2).lower() == "ms" else v

                    # Check shorthand
                    sh_match = re.search(r"(?<![a-zA-Z0-9_-])transition\s*:\s*([^;]+);?", body, re.IGNORECASE)
                    if sh_match:
                        raw_str = raw_str or sh_match.group(0)
                        parts = re.split(r",\s*(?![^(]*\))", sh_match.group(1).strip())
                        for part in parts:
                            p_dur, p_tf, p_delay = self._parse_transition_clause(part)
                            if dur_val is None and p_dur is not None:
                                dur_val = p_dur
                            if tf_val is None and p_tf is not None:
                                tf_val = p_tf
                            if delay_val is None and p_delay is not None:
                                delay_val = p_delay

                    if dur_val is not None or tf_val is not None:
                        clean_sel = sel.split(",")[0].strip()
                        if claimed_targets and any(ct in clean_sel for ct in claimed_targets):
                            continue
                        resolved_dur = dur_val if dur_val is not None else default_duration
                        resolved_tf = tf_val or default_easing
                        entry = {
                            "duration": round(resolved_dur, 2),
                            "type": "tween",
                            "timing_function": resolved_tf,
                            "easing": resolved_tf,
                            "ease": resolved_tf,
                            "raw": raw_str,
                        }
                        if delay_val is not None:
                            entry["delay"] = round(delay_val, 2)
                        element_transitions[clean_sel] = entry
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
                if claimed_targets and (target in claimed_targets or any(c in claimed_targets for c in classes)):
                    continue
                motion_triggers.append({
                    "trigger": "in_view",
                    "target": target,
                    "adapter": "standard",
                    "effect": effect,
                    "transition": {
                        "delay": float(delay) / 1000.0 if delay.isdigit() else 0.0,
                        "duration": float(duration) / 1000.0 if duration.isdigit() else 0.8,
                        "timing_function": default_easing,
                        "easing": default_easing,
                        "ease": default_easing,
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
            "easing": default_easing,
            "ease": default_easing,
        }
