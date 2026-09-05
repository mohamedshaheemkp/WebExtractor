from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FontFamilyDefinition:
    name: str
    fallbacks: list[str] = field(default_factory=list)
    weights: list[int] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    source: str = "system"  # "local" | "remote" | "system"
    local_path: str | None = None
    resolved: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TypographyRoleDefinition:
    font_family: str
    font_size: str
    font_weight: str
    line_height: str
    letter_spacing: str = "normal"
    text_transform: str = "none"
    text_decoration: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TypographyEngine:
    """
    Extracts, normalizes, and classifies typography from computed DOM observations,
    stylesheets, and font assets into a deterministic, IR-driven typography system.
    """

    SEMANTIC_ROLES = [
        "display",
        "hero",
        "heading",
        "subheading",
        "body",
        "caption",
        "label",
        "navigation",
        "button",
        "mono",
    ]

    def analyze(
        self,
        rendered_dom: dict[str, Any] | None,
        viewports: dict[str, Any],
        asset_manifest: list[dict[str, Any]],
        css_content: str = "",
    ) -> dict[str, Any]:
        desktop_dom = viewports.get("desktop", {}).get("dom") or rendered_dom
        mobile_dom = viewports.get("mobile", {}).get("dom")

        # 1. Collect all nodes from desktop DOM
        desktop_nodes: list[dict[str, Any]] = []
        if desktop_dom:
            self._collect_nodes(desktop_dom, desktop_nodes)

        # 2. Collect nodes from mobile DOM
        mobile_nodes: list[dict[str, Any]] = []
        if mobile_dom:
            self._collect_nodes(mobile_dom, mobile_nodes)

        # 3. Extract and parse font families
        font_families = self._extract_font_families(desktop_nodes, asset_manifest, css_content)

        # 4. Normalize observed typography into semantic roles
        roles = self._normalize_semantic_roles(desktop_nodes, font_families)

        # 5. Extract responsive typography differences (Desktop vs Mobile)
        responsive_overrides = self._extract_responsive_typography(desktop_nodes, mobile_nodes, roles)

        return {
            "font_families": [f.to_dict() for f in font_families],
            "roles": {role: defn.to_dict() for role, defn in sorted(roles.items())},
            "responsive": {
                "mobile": {role: diff for role, diff in sorted(responsive_overrides.items())}
            } if responsive_overrides else {},
        }

    def parse_font_stack(self, raw_family: str | None) -> tuple[str, list[str]]:
        """Parses a CSS font-family string into primary family and fallback list."""
        if not raw_family or not raw_family.strip():
            return "system-ui", ["-apple-system", "sans-serif"]

        parts = [
            p.strip().strip("'").strip('"')
            for p in raw_family.split(",")
            if p.strip()
        ]

        if not parts:
            return "system-ui", ["-apple-system", "sans-serif"]

        primary = parts[0]
        fallbacks = parts[1:] if len(parts) > 1 else ["sans-serif"]
        return primary, fallbacks

    def _collect_nodes(self, node: dict[str, Any] | None, acc: list[dict[str, Any]]) -> None:
        if not node:
            return
        acc.append(node)
        for child in node.get("children", []):
            self._collect_nodes(child, acc)

    def _extract_font_families(
        self,
        nodes: list[dict[str, Any]],
        asset_manifest: list[dict[str, Any]],
        css_content: str,
    ) -> list[FontFamilyDefinition]:
        observed_stacks: Counter = Counter()
        weights_per_family: dict[str, set[int]] = {}
        styles_per_family: dict[str, set[str]] = {}

        for n in nodes:
            st = n.get("styles", {})
            fam = st.get("fontFamily")
            if fam:
                observed_stacks[fam] += 1
                primary, _ = self.parse_font_stack(fam)

                # Track weights
                w = st.get("fontWeight")
                if w:
                    try:
                        int_w = int(w)
                        weights_per_family.setdefault(primary, set()).add(int_w)
                    except ValueError:
                        pass

                # Track styles
                fs = st.get("fontStyle")
                if fs and fs not in ("normal", ""):
                    styles_per_family.setdefault(primary, set()).add(fs)

        # Parse @font-face rules from CSS content if present
        font_face_families = re.findall(r"@font-face\s*{[^}]*font-family:\s*['\"]?([^'\";]+)['\"]?", css_content, re.IGNORECASE)
        for ff in font_face_families:
            observed_stacks[ff.strip()] += 1

        font_assets = [a for a in asset_manifest if a.get("category") == "fonts"]

        definitions: list[FontFamilyDefinition] = []
        seen_primaries = set()

        for raw_stack, _ in observed_stacks.most_common():
            primary, fallbacks = self.parse_font_stack(raw_stack)
            if primary.lower() in seen_primaries:
                continue
            seen_primaries.add(primary.lower())

            # Correlate with downloaded font files
            clean_p = re.sub(r"[\s\-_]+", "", primary.lower())
            matched_asset = next(
                (
                    a for a in font_assets
                    if clean_p in re.sub(r"[\s\-_]+", "", a.get("source", "").lower())
                    or clean_p in re.sub(r"[\s\-_]+", "", a.get("local", "").lower())
                ),
                None
            )

            weights = sorted(weights_per_family.get(primary, {400, 600}))
            styles = sorted(styles_per_family.get(primary, {"normal"}))

            definitions.append(
                FontFamilyDefinition(
                    name=primary,
                    fallbacks=fallbacks,
                    weights=weights,
                    styles=styles,
                    source="local" if matched_asset else ("system" if primary.lower() in ("system-ui", "sans-serif", "serif", "monospace", "arial", "helvetica") else "remote"),
                    local_path=matched_asset.get("local") if matched_asset else None,
                    resolved=bool(matched_asset) if matched_asset else (primary.lower() in ("system-ui", "sans-serif", "serif", "monospace", "arial", "helvetica")),
                )
            )

        if not definitions:
            definitions.append(
                FontFamilyDefinition(
                    name="Inter",
                    fallbacks=["system-ui", "-apple-system", "sans-serif"],
                    weights=[400, 500, 600, 700],
                    styles=["normal"],
                    source="system",
                    resolved=True,
                )
            )

        # Deterministic sorting by family name
        return sorted(definitions, key=lambda x: x.name)

    def _normalize_semantic_roles(
        self,
        nodes: list[dict[str, Any]],
        font_families: list[FontFamilyDefinition],
    ) -> dict[str, TypographyRoleDefinition]:
        display_fam = font_families[0].name if font_families else "system-ui"
        body_fam = font_families[-1].name if font_families else "sans-serif"

        # Check for explicitly distinctive display family
        for f in font_families:
            if any(k in f.name.lower() for k in ("display", "clash", "grotesk", "syne", "monument")):
                display_fam = f.name
                break

        # Defaults for semantic roles
        roles: dict[str, TypographyRoleDefinition] = {
            "display": TypographyRoleDefinition(
                font_family=display_fam,
                font_size="96px",
                font_weight="800",
                line_height="1.02",
                letter_spacing="-0.03em",
            ),
            "hero": TypographyRoleDefinition(
                font_family=display_fam,
                font_size="72px",
                font_weight="800",
                line_height="1.05",
                letter_spacing="-0.02em",
            ),
            "heading": TypographyRoleDefinition(
                font_family=display_fam,
                font_size="40px",
                font_weight="700",
                line_height="1.15",
                letter_spacing="-0.01em",
            ),
            "subheading": TypographyRoleDefinition(
                font_family=display_fam,
                font_size="24px",
                font_weight="600",
                line_height="1.25",
            ),
            "body": TypographyRoleDefinition(
                font_family=body_fam,
                font_size="16px",
                font_weight="400",
                line_height="1.6",
            ),
            "caption": TypographyRoleDefinition(
                font_family=body_fam,
                font_size="13px",
                font_weight="400",
                line_height="1.5",
            ),
            "label": TypographyRoleDefinition(
                font_family=body_fam,
                font_size="12px",
                font_weight="600",
                line_height="1.2",
                letter_spacing="0.12em",
                text_transform="uppercase",
            ),
            "navigation": TypographyRoleDefinition(
                font_family=body_fam,
                font_size="14px",
                font_weight="500",
                line_height="1.4",
            ),
            "button": TypographyRoleDefinition(
                font_family=body_fam,
                font_size="15px",
                font_weight="600",
                line_height="1.2",
            ),
            "mono": TypographyRoleDefinition(
                font_family="ui-monospace, monospace",
                font_size="14px",
                font_weight="400",
                line_height="1.5",
            ),
        }

        # Override with real observed values from matching DOM nodes
        for n in nodes:
            tag = n.get("tag", "").lower()
            st = n.get("styles", {})
            if not st:
                continue

            fs = st.get("fontSize")
            fw = st.get("fontWeight")
            lh = st.get("lineHeight")
            ls = st.get("letterSpacing")
            tt = st.get("textTransform")
            ff = st.get("fontFamily")
            primary_ff = self.parse_font_stack(ff)[0] if ff else None

            # H1 -> Hero / Display
            if tag == "h1" and fs:
                px = self._to_px_int(fs)
                role_key = "display" if px >= 80 else "hero"
                roles[role_key] = TypographyRoleDefinition(
                    font_family=primary_ff or roles[role_key].font_family,
                    font_size=fs,
                    font_weight=str(fw or roles[role_key].font_weight),
                    line_height=str(lh or roles[role_key].line_height),
                    letter_spacing=ls or roles[role_key].letter_spacing,
                    text_transform=tt or roles[role_key].text_transform,
                )

            # H2 -> Heading
            elif tag == "h2" and fs:
                roles["heading"] = TypographyRoleDefinition(
                    font_family=primary_ff or roles["heading"].font_family,
                    font_size=fs,
                    font_weight=str(fw or roles["heading"].font_weight),
                    line_height=str(lh or roles["heading"].line_height),
                    letter_spacing=ls or roles["heading"].letter_spacing,
                    text_transform=tt or roles["heading"].text_transform,
                )

            # H3 -> Subheading
            elif tag == "h3" and fs:
                roles["subheading"] = TypographyRoleDefinition(
                    font_family=primary_ff or roles["subheading"].font_family,
                    font_size=fs,
                    font_weight=str(fw or roles["subheading"].font_weight),
                    line_height=str(lh or roles["subheading"].line_height),
                    letter_spacing=ls or roles["subheading"].letter_spacing,
                    text_transform=tt or roles["subheading"].text_transform,
                )

            # P / body text
            elif tag == "p" and fs:
                px = self._to_px_int(fs)
                if 14 <= px <= 18:
                    roles["body"] = TypographyRoleDefinition(
                        font_family=primary_ff or roles["body"].font_family,
                        font_size=fs,
                        font_weight=str(fw or roles["body"].font_weight),
                        line_height=str(lh or roles["body"].line_height),
                        letter_spacing=ls or roles["body"].letter_spacing,
                    )
                elif px <= 13:
                    roles["caption"] = TypographyRoleDefinition(
                        font_family=primary_ff or roles["caption"].font_family,
                        font_size=fs,
                        font_weight=str(fw or roles["caption"].font_weight),
                        line_height=str(lh or roles["caption"].line_height),
                    )

            # Uppercase labels
            if tt == "uppercase" and fs:
                roles["label"] = TypographyRoleDefinition(
                    font_family=primary_ff or roles["label"].font_family,
                    font_size=fs,
                    font_weight=str(fw or roles["label"].font_weight),
                    line_height=str(lh or roles["label"].line_height),
                    letter_spacing=ls or "0.15em",
                    text_transform="uppercase",
                )

            # Button
            if tag == "button" and fs:
                roles["button"] = TypographyRoleDefinition(
                    font_family=primary_ff or roles["button"].font_family,
                    font_size=fs,
                    font_weight=str(fw or roles["button"].font_weight),
                    line_height=str(lh or roles["button"].line_height),
                    letter_spacing=ls or roles["button"].letter_spacing,
                )

        return roles

    def _extract_responsive_typography(
        self,
        desktop_nodes: list[dict[str, Any]],
        mobile_nodes: list[dict[str, Any]],
        roles: dict[str, TypographyRoleDefinition],
    ) -> dict[str, dict[str, str]]:
        overrides: dict[str, dict[str, str]] = {}

        # Look for differences in h1, h2, h3 between desktop and mobile
        def find_by_tag(nodes: list[dict[str, Any]], tag: str) -> dict[str, Any] | None:
            return next((n for n in nodes if n.get("tag", "").lower() == tag and n.get("styles", {}).get("fontSize")), None)

        for tag, role in (("h1", "hero"), ("h2", "heading"), ("h3", "subheading")):
            d_node = find_by_tag(desktop_nodes, tag)
            m_node = find_by_tag(mobile_nodes, tag)

            if d_node and m_node:
                d_fs = d_node.get("styles", {}).get("fontSize")
                m_fs = m_node.get("styles", {}).get("fontSize")

                if d_fs and m_fs and d_fs != m_fs:
                    overrides[role] = {"font_size": m_fs}
                    m_lh = m_node.get("styles", {}).get("lineHeight")
                    if m_lh:
                        overrides[role]["line_height"] = m_lh

        # If no explicit diff observed, provide proportional responsive scaling for large headings
        if not overrides:
            hero_fs = roles.get("hero", roles["display"]).font_size
            px = self._to_px_int(hero_fs)
            if px > 48:
                overrides["hero"] = {"font_size": f"{max(36, int(px * 0.65))}px"}
                overrides["display"] = {"font_size": f"{max(40, int(px * 0.7))}px"}

        return overrides

    def _to_px_int(self, val: str) -> int:
        match = re.search(r"(\d+)", val)
        return int(match.group(1)) if match else 16
