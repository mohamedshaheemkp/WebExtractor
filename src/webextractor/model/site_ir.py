from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SiteIR:
    """
    Complete Intermediate Representation (IR) of a reverse-engineered website.
    Acts as the single contract between extraction/analysis and generator.
    """

    metadata: dict[str, Any]
    routes: list[str]
    design_system: dict[str, Any]
    responsive_rules: list[dict[str, Any]] = field(default_factory=list)
    pages: list[dict[str, Any]] = field(default_factory=list)
    reusable_components: list[dict[str, Any]] = field(default_factory=list)
    component_styles: dict[str, dict[str, Any]] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    components: dict[str, Any] | None = None
    assets: list[dict[str, Any]] = field(default_factory=list)
    asset_bindings: list[dict[str, Any]] = field(default_factory=list)
    typography: dict[str, Any] = field(default_factory=dict)
    layout: dict[str, Any] = field(default_factory=dict)
    raw_tokens: dict[str, Any] | None = None
    screenshot_paths: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, output_dir: str | Path) -> None:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)

        ir_dict = self.to_dict()

        # Write canonical source-ir.json and site_ir.json
        (path / "source-ir.json").write_text(
            json.dumps(ir_dict, indent=2),
            encoding="utf-8",
        )
        (path / "site_ir.json").write_text(
            json.dumps(ir_dict, indent=2),
            encoding="utf-8",
        )
        (path / "design_system.json").write_text(
            json.dumps(self.design_system, indent=2),
            encoding="utf-8",
        )
        (path / "typography.json").write_text(
            json.dumps(self.typography, indent=2),
            encoding="utf-8",
        )
        (path / "layout.json").write_text(
            json.dumps(self.layout, indent=2),
            encoding="utf-8",
        )
        (path / "components.json").write_text(
            json.dumps(
                {
                    "pages": self.pages,
                    "reusable": self.reusable_components,
                    "tree": self.components,
                    "styles": self.component_styles,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (path / "responsive.json").write_text(
            json.dumps(self.responsive_rules, indent=2),
            encoding="utf-8",
        )
        (path / "asset_bindings.json").write_text(
            json.dumps(self.asset_bindings, indent=2),
            encoding="utf-8",
        )



