from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class TriggerSpec(BaseModel):
    type: str  # "click", "hover", "focus", "press", "scroll", "mount"
    selector: str
    target_id: str | None = None
    event_options: dict[str, Any] = Field(default_factory=dict)


class ActionSpec(BaseModel):
    type: str  # "toggle", "open", "close", "navigate", "state_change", "animate", "carousel_step"
    target: str | None = None
    target_route: str | None = None
    transition: dict[str, Any] = Field(default_factory=dict)


class InteractionIR(BaseModel):
    """
    Universal Interaction Intermediate Representation (IR).
    Represents an observed behavioral relationship between triggers, actions, and states.
    Completely decoupled from framework-specific or site-specific names.
    """
    id: str
    category: str = "generic"  # "menu", "accordion", "tabs", "modal", "dropdown", "cursor", "route_transition", "carousel", "generic"
    trigger: TriggerSpec
    action: ActionSpec
    states: dict[str, dict[str, Any]] = Field(default_factory=dict)
    animation: dict[str, Any] = Field(default_factory=dict)
    conditions: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class Interaction(BaseModel):
    """Legacy compatibility model for simple trigger-action declarations."""
    trigger: str  # hover, click, scroll, load
    selector: str
    target: str | None = None
    action: str = ""  # animate, open_modal, toggle_class, navigate
    animation_details: dict[str, str] = Field(default_factory=dict)
    description: str = ""
