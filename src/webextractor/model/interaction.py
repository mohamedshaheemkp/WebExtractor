from __future__ import annotations

from pydantic import BaseModel, Field


class Interaction(BaseModel):
    trigger: str  # hover, click, scroll, load
    selector: str
    target: str | None = None
    action: str = ""  # animate, open_modal, toggle_class, navigate
    animation_details: dict[str, str] = Field(default_factory=dict)
    description: str = ""
