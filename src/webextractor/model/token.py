from __future__ import annotations

from pydantic import BaseModel, Field


class ColorToken(BaseModel):
    name: str
    value: str
    usage_count: int = 1


class TypographyToken(BaseModel):
    name: str
    font_family: str
    font_size: str | None = None
    font_weight: str | None = None
    line_height: str | None = None


class SpacingToken(BaseModel):
    name: str
    value: str


class DesignTokens(BaseModel):
    colors: list[ColorToken] = Field(default_factory=list)
    typography: list[TypographyToken] = Field(default_factory=list)
    spacings: list[SpacingToken] = Field(default_factory=list)
    border_radii: list[str] = Field(default_factory=list)
    shadows: list[str] = Field(default_factory=list)
