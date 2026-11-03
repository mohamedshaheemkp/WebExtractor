from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LayoutViolation:
    violation_type: str  # 'OVERLAY_COLLISION', 'TRACK_CLAMPED', 'VIEWPORT_SHRINK', 'MEDIA_AUTOPLAY_MISSING'
    identifier: str
    target_element: str
    details: dict[str, Any]
    severity: str = "ERROR"  # 'WARNING' or 'ERROR'


class SpatialComparator:
    """Compares baseline vs reconstructed spatial trees and outputs actionable layout violations."""

    def __init__(self, baseline_nodes: list[dict[str, Any]], reconstructed_nodes: list[dict[str, Any]]):
        self.baseline_nodes = baseline_nodes
        self.reconstructed_nodes = reconstructed_nodes
        self._baseline_map = {n["identifier"]: n for n in baseline_nodes}
        self._reconstructed_map = {n["identifier"]: n for n in reconstructed_nodes}

    def compare(self) -> list[LayoutViolation]:
        violations: list[LayoutViolation] = []
        
        violations.extend(self._check_overlay_collisions())
        violations.extend(self._check_horizontal_tracks())
        violations.extend(self._check_viewport_shrinkage())
        violations.extend(self._check_media_autoplay())

        return violations

    def _check_overlay_collisions(self) -> list[LayoutViolation]:
        """Detects if navigation or footer elements collided into main content areas."""
        violations = []
        overlay_tags = {"header", "nav", "footer"}

        for r_node in self.reconstructed_nodes:
            is_overlay = r_node["tag"] in overlay_tags or "nav" in r_node["className"].lower() or "footer" in r_node["className"].lower()
            if not is_overlay:
                continue

            r_rect = r_node["rect"]
            b_node = self._baseline_map.get(r_node["identifier"])

            # Check if element was pinned/fixed at viewport boundary in baseline but shifted inside center in rebuild
            if b_node:
                b_rect = b_node["rect"]
                # Vertical anchoring drifted into the vertical center
                if b_rect["top"] < 100 and r_rect["top"] > 150:
                    violations.append(LayoutViolation(
                        violation_type="OVERLAY_COLLISION",
                        identifier=r_node["identifier"],
                        target_element=r_node["tag"],
                        details={
                            "role": "header",
                            "expected_top": b_rect["top"],
                            "actual_top": r_rect["top"],
                            "recommended_style": "position: fixed; top: 0; left: 0; width: 100%; z-index: 50;"
                        }
                    ))
                elif b_rect["bottom"] > 700 and r_rect["bottom"] < 600:
                    violations.append(LayoutViolation(
                        violation_type="OVERLAY_COLLISION",
                        identifier=r_node["identifier"],
                        target_element=r_node["tag"],
                        details={
                            "role": "footer",
                            "expected_bottom": b_rect["bottom"],
                            "actual_bottom": r_rect["bottom"],
                            "recommended_style": "position: fixed; bottom: 0; left: 0; width: 100%; z-index: 50;"
                        }
                    ))

        return violations

    def _check_horizontal_tracks(self) -> list[LayoutViolation]:
        """Detects horizontal carousel tracks that got clipped or lost their flex-row dimensions."""
        violations = []

        for b_id, b_node in self._baseline_map.items():
            # Check if this container held horizontal content extending beyond viewport width
            if b_node["rect"]["width"] > 1600 or "carousel" in b_node["className"].lower() or "track" in b_node["className"].lower():
                r_node = self._reconstructed_map.get(b_id)
                if r_node:
                    r_width = r_node["rect"]["width"]
                    # If reconstructed track collapsed to standard screen width or intrinsic card width
                    if r_width < (b_node["rect"]["width"] * 0.7):
                        violations.append(LayoutViolation(
                            violation_type="TRACK_CLAMPED",
                            identifier=b_id,
                            target_element=r_node["tag"],
                            details={
                                "baseline_width": b_node["rect"]["width"],
                                "reconstructed_width": r_width,
                                "recommended_style": "display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; width: max-content !important;"
                            }
                        ))

        return violations

    def _check_viewport_shrinkage(self) -> list[LayoutViolation]:
        """Detects if root containers or main sections collapsed into intrinsic boxes."""
        violations = []
        for r_node in self.reconstructed_nodes:
            if r_node["tag"] in {"main", "body"} or r_node["framerName"] == "Page":
                if r_node["rect"]["width"] < 1000:  # Collapsed into ~729px box
                    violations.append(LayoutViolation(
                        violation_type="VIEWPORT_SHRINK",
                        identifier=r_node["identifier"],
                        target_element=r_node["tag"],
                        details={
                            "actual_width": r_node["rect"]["width"],
                            "recommended_style": "width: 100vw; min-height: 100vh; overflow-x: hidden;"
                        }
                    ))
        return violations

    def _check_media_autoplay(self) -> list[LayoutViolation]:
        """Detects videos missing autoplay/muted/playsInline configurations."""
        violations = []
        for r_node in self.reconstructed_nodes:
            if r_node["tag"] == "video":
                attrs = r_node.get("videoAttributes") or {}
                if not (attrs.get("autoplay") and attrs.get("muted") and attrs.get("playsInline")):
                    violations.append(LayoutViolation(
                        violation_type="MEDIA_AUTOPLAY_MISSING",
                        identifier=r_node["identifier"],
                        target_element="video",
                        details={
                            "attributes": attrs,
                            "required": ["autoPlay", "muted", "loop", "playsInline"]
                        }
                    ))
        return violations

