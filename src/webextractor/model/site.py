from __future__ import annotations

from pydantic import BaseModel, Field

from webextractor.model.asset import Asset
from webextractor.model.page import Page
from webextractor.model.route import Route
from webextractor.model.token import DesignTokens


class Site(BaseModel):
    name: str
    url: str
    framework: str | None = None
    pages: list[Page] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    tokens: DesignTokens = Field(default_factory=DesignTokens)
    api_endpoints: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
