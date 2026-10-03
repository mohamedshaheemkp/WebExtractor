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

    @staticmethod
    def _targets_overlap(t1_target: str, t1_id: str | None, t2_target: str, t2_id: str | None) -> bool:
        """Return True if two triggers target the same DOM element."""
        if t1_id and t2_id and t1_id == t2_id:
            return True
        if t1_target and t2_target and t1_target == t2_target:
            return True
        if t1_id and t2_target and (t1_id == t2_target or f'"{t1_id}"' in t2_target or f"'{t1_id}'" in t2_target or t1_id in t2_target):
            return True
        if t2_id and t1_target and (t2_id == t1_target or f'"{t2_id}"' in t1_target or f"'{t2_id}'" in t1_target or t2_id in t1_target):
            return True
        return False

    @staticmethod
    def _extract_property_set(trigger: dict[str, Any]) -> set[str]:
        """Extract the set of animated properties for this trigger."""
        props = set()
        initial = trigger.get("initial", {}) or {}
        animate = trigger.get("animate", {}) or {}
        props.update(initial.keys())
        props.update(animate.keys())
        if trigger.get("effect"):
            props.add(trigger["effect"])
        if not props:
            props.update(["opacity", "transform"])
        return props

    @classmethod
    def reconcile_motion_triggers(
        cls,
        existing: list[dict[str, Any]],
        incoming: list[dict[str, Any]],
        adapter_name: str = "",
    ) -> None:
        """
        Reconcile motion_triggers so there is at most one trigger per (target, property-set).
        Records the winning adapter.
        """
        for new_trg in incoming:
            if adapter_name and not new_trg.get("adapter"):
                new_trg["adapter"] = adapter_name

            new_target = new_trg.get("target", "")
            new_id = new_trg.get("id")
            new_props = cls._extract_property_set(new_trg)

            match = None
            for ex_trg in existing:
                ex_target = ex_trg.get("target", "")
                ex_id = ex_trg.get("id")
                if cls._targets_overlap(new_target, new_id, ex_target, ex_id):
                    ex_props = cls._extract_property_set(ex_trg)
                    if not new_props or not ex_props or bool(new_props & ex_props):
                        match = ex_trg
                        break

            if match is None:
                existing.append(new_trg)
            else:
                # Existing trigger from earlier higher-priority adapter wins
                if not match.get("adapter"):
                    match["adapter"] = match.get("source") or "framer"
                for k, v in new_trg.items():
                    if k == "transition":
                        match.setdefault("transition", {})
                        for tk, tv in (v or {}).items():
                            match["transition"].setdefault(tk, tv)
                    elif k not in match:
                        match[k] = v

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

        claimed_targets: set[str] = set()

        for adapter in self.adapters:
            if adapter.can_handle(html_content, css_content):
                adapter_name = "framer" if "framer" in adapter.__class__.__name__.lower() else (
                    "standard" if "standard" in adapter.__class__.__name__.lower() else adapter.__class__.__name__.lower()
                )
                res = adapter.extract_motion(html_content, css_content, claimed_targets=claimed_targets)

                # Track claimed targets from this adapter
                for app_id in res.get("appear_animations", {}):
                    claimed_targets.add(app_id)
                for trg in res.get("motion_triggers", []):
                    if trg.get("id"):
                        claimed_targets.add(trg["id"])
                    if trg.get("target"):
                        claimed_targets.add(trg["target"])
                for sel in res.get("parallax_elements", []):
                    claimed_targets.add(sel)

                merged["appear_animations"].update(res.get("appear_animations", {}))
                if res.get("element_transitions"):
                    for sel, t_data in res["element_transitions"].items():
                        if not any(ct in sel for ct in claimed_targets):
                            merged["element_transitions"].setdefault(sel, t_data)
                        elif sel not in merged["element_transitions"]:
                            merged["element_transitions"][sel] = t_data

                merged["keyframes"].extend(res.get("keyframes", []))
                if res.get("has_cursor"):
                    merged["has_cursor"] = True
                if res.get("has_time_component"):
                    merged["has_time_component"] = True
                merged["parallax_elements"].extend(res.get("parallax_elements", []))

                # Reconcile motion triggers ensuring at most one per (target, property-set)
                self.reconcile_motion_triggers(
                    merged["motion_triggers"],
                    res.get("motion_triggers", []),
                    adapter_name=adapter_name,
                )

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
