from __future__ import annotations

from pydantic import BaseModel, Field


class Route(BaseModel):
    path: str
    url: str
    name: str
    title: str = ""
    is_external: bool = False
    sub_routes: list[str] = Field(default_factory=list)
