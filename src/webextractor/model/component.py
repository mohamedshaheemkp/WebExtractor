from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ComponentNode(BaseModel):
    name: str
    category: str = "general"  # hero, navbar, footer, card, section, button, form, media
    tag_name: str = "div"
    text_content: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    styles: dict[str, str] = Field(default_factory=dict)
    tailwind_classes: list[str] = Field(default_factory=list)
    children: list[ComponentNode] = Field(default_factory=list)
    props: dict[str, Any] = Field(default_factory=dict)
    jsx_snippet: str = ""
