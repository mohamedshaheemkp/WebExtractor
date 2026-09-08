from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseMotionAdapter(ABC):
    """
    Abstract interface for platform-specific motion and animation evidence extraction.
    Adapters parse raw HTML/CSS/script signatures and convert them into
    normalized motion metadata.
    """

    @abstractmethod
    def can_handle(self, html: str, css: str = "") -> bool:
        """Return True if this adapter detects its platform signatures in the source evidence."""
        pass

    @abstractmethod
    def extract_motion(self, html: str, css: str = "") -> dict[str, Any]:
        """
        Extract motion configurations and return a dictionary conforming to the normalized schema:
        {
            "appear_animations": dict[str, Any],  # Keyed by target selector or ID
            "keyframes": list[dict[str, Any]],
            "has_cursor": bool,
            "has_time_component": bool,
            "parallax_elements": list[str],
            "motion_triggers": list[dict[str, Any]],
        }
        """
        pass
