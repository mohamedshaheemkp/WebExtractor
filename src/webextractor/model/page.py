from __future__ import annotations

from pydantic import BaseModel, Field

from webextractor.model.component import ComponentNode
from webextractor.model.interaction import Interaction


class Page(BaseModel):
    url: str
    route_path: str = "/"
    title: str = ""
    description: str = ""
    components: list[ComponentNode] = Field(default_factory=list)
    interactions: list[Interaction] = Field(default_factory=list)
    raw_html: str = ""
    screenshot_path: str | None = None
