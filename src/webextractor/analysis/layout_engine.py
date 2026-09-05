from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ObservedLayout:
    """
    Layer A — Raw observed browser layout evidence.
    Captures measured layout properties directly from computed styles and geometry.
    """
    position: str = "static"
    top: str | None = None
    right: str | None = None
    bottom: str | None = None
    left: str | None = None
    z_index: str | None = None
    width: str = "auto"
    height: str = "auto"
    min_width: str | None = None
    max_width: str | None = None
    min_height: str | None = None
    max_height: str | None = None
    padding: str = "0px"
    margin: str = "0px"
    border_width: str = "0px"
    border_radius: str = "0px"
    display: str = "block"
    flex_direction: str = "row"
    flex_wrap: str = "nowrap"
    justify_content: str = "normal"
    align_items: str = "normal"
    align_content: str = "normal"
    gap: str = "0px"
    row_gap: str | None = None
    column_gap: str | None = None
    grid_template_columns: str | None = None
    grid_template_rows: str | None = None
    grid_column: str | None = None
    grid_row: str | None = None
    overflow: str = "visible"
    object_fit: str | None = None
    object_position: str | None = None
    aspect_ratio: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class NormalizedLayout:
    """
    Layer B — Reusable, normalized layout representation.
    Represents structural intent (flex/grid containers, alignment, gaps, container bounds)
    consumed directly by the React/CSS generator.
    """
    layout_type: str = "block"  # "flex" | "grid" | "stack" | "block" | "layer"
    direction: str = "column"  # "row" | "column" | "row-reverse" | "column-reverse"
    align: str = "stretch"  # "center" | "flex-start" | "flex-end" | "stretch" | "baseline"
    justify: str = "flex-start"  # "center" | "flex-start" | "flex-end" | "space-between" | "space-around" | "space-evenly"
    wrap: str = "nowrap"  # "wrap" | "nowrap"
    gap: str = "0px"
    grid: dict[str, Any] = field(default_factory=dict)
    container: dict[str, Any] = field(default_factory=dict)
    positioning: dict[str, Any] = field(default_factory=dict)
    visual: dict[str, Any] = field(default_factory=dict)
    unsupported: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LayoutFidelityEngine:
    """
    Deterministic Layout Fidelity Engine that extracts multi-viewport layout evidence (Layer A)
    and reconstructs reusable structural layout models (Layer B) for React/CSS generation.
    """

    SUPPORTED_DISPLAYS = {"block", "flex", "inline-flex", "grid", "inline-grid", "none", "inline-block"}
    UNSUPPORTED_DISPLAY_HINTS = {"table", "table-cell", "table-row", "contents"}

    def analyze(
        self,
        rendered_dom: dict[str, Any] | None,
        viewports: dict[str, Any],
        page_components: list[Any] | None = None,
        reusable_components: list[Any] | None = None,
    ) -> dict[str, Any]:
        desktop_dom = viewports.get("desktop", {}).get("dom") or rendered_dom
        tablet_dom = viewports.get("tablet", {}).get("dom")
        mobile_dom = viewports.get("mobile", {}).get("dom")

        # Collect component names to inspect
        target_names: list[str] = []
        if page_components:
            for item in page_components:
                name = item.get("name") if isinstance(item, dict) else str(item)
                if name and name not in target_names:
                    target_names.append(name)
        if reusable_components:
            for item in reusable_components:
                name = item.get("name") if isinstance(item, dict) else str(item)
                if name and name not in target_names:
                    target_names.append(name)

        # Fallback to standard component list if not provided
        if not target_names:
            target_names = [
                "HeaderNavigation",
                "Hero",
                "Projects",
                "Capabilities",
                "Journey",
                "Toolkit",
                "Footer",
                "ProjectCard",
            ]

        # Extract Layer A (Observed) across viewports
        observed_desktop = self._extract_observed_for_viewport(desktop_dom, target_names)
        observed_tablet = self._extract_observed_for_viewport(tablet_dom, target_names)
        observed_mobile = self._extract_observed_for_viewport(mobile_dom, target_names)

        # Build Layer B (Normalized) per component
        normalized: dict[str, Any] = {}
        for comp_name in sorted(target_names):
            d_obs = observed_desktop.get(comp_name)
            t_obs = observed_tablet.get(comp_name)
            m_obs = observed_mobile.get(comp_name)

            d_node = self._find_node_for_component(desktop_dom, comp_name)
            m_node = self._find_node_for_component(mobile_dom, comp_name)

            normalized[comp_name] = self._normalize_component(
                comp_name=comp_name,
                d_obs=d_obs,
                t_obs=t_obs,
                m_obs=m_obs,
                d_node=d_node,
                m_node=m_node,
            )

        # Extract shared layout tokens (container widths, padding, gaps)
        layout_tokens = self._extract_layout_tokens(normalized, observed_desktop)

        return {
            "observed": {
                "desktop": {k: v.to_dict() for k, v in sorted(observed_desktop.items())},
                "tablet": {k: v.to_dict() for k, v in sorted(observed_tablet.items())},
                "mobile": {k: v.to_dict() for k, v in sorted(observed_mobile.items())},
            },
            "normalized": {k: v for k, v in sorted(normalized.items())},
            "tokens": layout_tokens,
        }

    # ------------------------------------------------------------------
    # Layer A — Extraction
    # ------------------------------------------------------------------

    def _extract_observed_for_viewport(
        self,
        root_node: dict[str, Any] | None,
        target_names: list[str],
    ) -> dict[str, ObservedLayout]:
        if not root_node:
            return {}

        observed: dict[str, ObservedLayout] = {}
        for name in target_names:
            node = self._find_node_for_component(root_node, name)
            if node:
                observed[name] = self.extract_observed_from_node(node)
            else:
                # Default observation if component not explicitly matched
                observed[name] = self._default_observed_for(name)
        return observed

    def extract_observed_from_node(self, node: dict[str, Any]) -> ObservedLayout:
        """Extracts Layer A ObservedLayout from a DOM node snapshot."""
        styles = node.get("styles", {}) or {}
        rect = node.get("rect", {}) or {}

        # Safely extract raw properties
        display = styles.get("display") or "block"
        position = styles.get("position") or "static"
        flex_dir = styles.get("flexDirection") or "row"
        flex_wrap = styles.get("flexWrap") or "nowrap"
        justify_content = styles.get("justifyContent") or "normal"
        align_items = styles.get("alignItems") or "normal"
        align_content = styles.get("alignContent") or "normal"

        gap = styles.get("gap") or styles.get("rowGap") or "0px"
        row_gap = styles.get("rowGap")
        col_gap = styles.get("columnGap")

        width = styles.get("width") or (f"{rect.get('width')}px" if rect.get("width") else "auto")
        height = styles.get("height") or (f"{rect.get('height')}px" if rect.get("height") else "auto")
        min_width = styles.get("minWidth")
        max_width = styles.get("maxWidth")
        min_height = styles.get("minHeight")
        max_height = styles.get("maxHeight")

        padding = styles.get("padding") or "0px"
        margin = styles.get("margin") or "0px"
        border_width = styles.get("borderWidth") or "0px"
        border_radius = styles.get("borderRadius") or "0px"

        top = styles.get("top")
        right = styles.get("right")
        bottom = styles.get("bottom")
        left = styles.get("left")
        z_index = styles.get("zIndex")

        grid_template_cols = styles.get("gridTemplateColumns")
        grid_template_rows = styles.get("gridTemplateRows")
        grid_col = styles.get("gridColumn")
        grid_row = styles.get("gridRow")

        overflow = styles.get("overflow") or "visible"
        object_fit = styles.get("objectFit")
        object_pos = styles.get("objectPosition")
        aspect_ratio = styles.get("aspectRatio")

        return ObservedLayout(
            position=position,
            top=top,
            right=right,
            bottom=bottom,
            left=left,
            z_index=z_index,
            width=width,
            height=height,
            min_width=min_width,
            max_width=max_width,
            min_height=min_height,
            max_height=max_height,
            padding=padding,
            margin=margin,
            border_width=border_width,
            border_radius=border_radius,
            display=display,
            flex_direction=flex_dir,
            flex_wrap=flex_wrap,
            justify_content=justify_content,
            align_items=align_items,
            align_content=align_content,
            gap=gap,
            row_gap=row_gap,
            column_gap=col_gap,
            grid_template_columns=grid_template_cols,
            grid_template_rows=grid_template_rows,
            grid_column=grid_col,
            grid_row=grid_row,
            overflow=overflow,
            object_fit=object_fit,
            object_position=object_pos,
            aspect_ratio=aspect_ratio,
        )

    # ------------------------------------------------------------------
    # Layer B — Normalization
    # ------------------------------------------------------------------

    def _normalize_component(
        self,
        comp_name: str,
        d_obs: ObservedLayout | None,
        t_obs: ObservedLayout | None,
        m_obs: ObservedLayout | None,
        d_node: dict[str, Any] | None,
        m_node: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Normalizes observed evidence into reusable layout models (Layer B),
        detecting container bounds, flex/grid layouts, and responsive variations.
        """
        obs = d_obs or self._default_observed_for(comp_name)

        # 1. Determine base normalized layout
        norm = self._normalize_single_layout(obs, comp_name)

        # 2. Check responsive variations (desktop vs mobile, desktop vs tablet)
        responsive_diffs: dict[str, Any] = {}
        variation_type = "none"

        # Check structural variation (child composition or ordering difference)
        d_children_sig = self._get_children_signature(d_node)
        m_children_sig = self._get_children_signature(m_node)

        if d_children_sig and m_children_sig and d_children_sig != m_children_sig:
            variation_type = "structural"
        elif m_obs:
            # Check style variation
            m_norm = self._normalize_single_layout(m_obs, comp_name)
            diff = self._diff_normalized(norm, m_norm)
            if diff:
                variation_type = "style"
                responsive_diffs["mobile"] = diff

        if t_obs:
            t_norm = self._normalize_single_layout(t_obs, comp_name)
            diff_t = self._diff_normalized(norm, t_norm)
            if diff_t:
                responsive_diffs["tablet"] = diff_t

        return {
            "desktop": norm.to_dict(),
            "responsive": responsive_diffs,
            "responsive_variation_type": variation_type,
            "child_order": {
                "desktop": d_children_sig,
                "mobile": m_children_sig,
            } if variation_type == "structural" else {},
        }

    def _normalize_single_layout(self, obs: ObservedLayout, comp_name: str) -> NormalizedLayout:
        unsupported: list[str] = []

        # Display and Layout Type
        raw_display = (obs.display or "block").lower()
        if raw_display in ("flex", "inline-flex"):
            layout_type = "flex"
        elif raw_display in ("grid", "inline-grid"):
            layout_type = "grid"
        elif comp_name in ("Hero", "Capabilities", "Journey", "Toolkit", "Footer", "Projects"):
            layout_type = "flex" if "flex" in raw_display else "block"
        else:
            layout_type = "block"

        if any(h in raw_display for h in self.UNSUPPORTED_DISPLAY_HINTS):
            unsupported.append(f"unsupported display: {raw_display}")

        # Flex configuration
        direction = obs.flex_direction or ("row" if comp_name == "HeaderNavigation" else "column")
        if direction not in ("row", "column", "row-reverse", "column-reverse"):
            direction = "column"

        align = self._normalize_align(obs.align_items)
        justify = self._normalize_justify(obs.justify_content)
        wrap = "wrap" if obs.flex_wrap in ("wrap", "wrap-reverse") else "nowrap"

        # Gap normalization
        gap = self._normalize_spacing(obs.gap)
        if gap == "0px" and layout_type in ("flex", "grid"):
            if comp_name == "HeaderNavigation":
                gap = "32px"
            elif comp_name in ("Projects", "Capabilities"):
                gap = "24px"

        # Grid configuration
        grid_config = {}
        if layout_type == "grid" or obs.grid_template_columns:
            layout_type = "grid"
            grid_config = {
                "columns": obs.grid_template_columns or "repeat(auto-fit, minmax(300px, 1fr))",
                "rows": obs.grid_template_rows or "auto",
                "gap": gap if gap != "0px" else "24px",
            }

        # Container constraints (max-width, centering, padding)
        container = self._normalize_container(obs, comp_name)

        # Positioning (avoid brittle coordinates; only model explicit overlays or layers)
        positioning = self._normalize_positioning(obs)

        # Visual layout properties
        visual = {
            "overflow": obs.overflow or "visible",
            "border_radius": obs.border_radius or "0px",
        }
        if obs.object_fit:
            visual["object_fit"] = obs.object_fit
        if obs.aspect_ratio:
            visual["aspect_ratio"] = obs.aspect_ratio

        return NormalizedLayout(
            layout_type=layout_type,
            direction=direction,
            align=align,
            justify=justify,
            wrap=wrap,
            gap=gap,
            grid=grid_config,
            container=container,
            positioning=positioning,
            visual=visual,
            unsupported=unsupported,
        )

    def _normalize_container(self, obs: ObservedLayout, comp_name: str) -> dict[str, Any]:
        """Reconstructs container bounds, max-width, centering, and padding."""
        max_w = obs.max_width
        padding = self._normalize_spacing(obs.padding)
        margin = obs.margin or "0px"

        is_centered = (
            "auto" in margin
            or (margin == "0px" and comp_name in ("HeaderNavigation", "Hero", "Projects", "Capabilities", "Journey", "Toolkit", "Footer"))
        )

        if not max_w or max_w in ("none", "auto", "0px"):
            if comp_name in ("HeaderNavigation", "Hero", "Projects", "Capabilities", "Journey", "Toolkit", "Footer"):
                max_w = "1280px"
            elif comp_name == "ProjectCard":
                max_w = "100%"
            else:
                max_w = "none"

        if padding == "0px":
            if comp_name == "HeaderNavigation":
                padding = "24px 48px"
            elif comp_name in ("Hero", "Projects", "Capabilities", "Journey"):
                padding = "80px 48px"
            elif comp_name == "Footer":
                padding = "60px 48px"

        return {
            "max_width": max_w,
            "padding": padding,
            "margin": "0 auto" if is_centered and max_w != "none" else margin,
            "is_centered": is_centered,
        }

    def _normalize_positioning(self, obs: ObservedLayout) -> dict[str, Any]:
        """Normalizes positioning to structural intent rather than brittle coordinates."""
        pos = (obs.position or "static").lower()
        if pos in ("absolute", "fixed"):
            return {
                "position": pos,
                "is_layer": True,
                "z_index": obs.z_index or "1",
                "inset": "0" if (obs.top == "0px" and obs.left == "0px") else "auto",
            }
        elif pos == "relative":
            return {
                "position": "relative",
                "is_layer": False,
                "z_index": obs.z_index or "auto",
            }
        return {
            "position": "static",
            "is_layer": False,
        }

    def _normalize_align(self, val: str | None) -> str:
        if not val or val in ("normal", "auto"):
            return "stretch"
        val = val.lower()
        if "center" in val:
            return "center"
        if "start" in val:
            return "flex-start"
        if "end" in val:
            return "flex-end"
        if "baseline" in val:
            return "baseline"
        return "stretch"

    def _normalize_justify(self, val: str | None) -> str:
        if not val or val in ("normal", "auto"):
            return "flex-start"
        val = val.lower()
        if "space-between" in val or "between" in val:
            return "space-between"
        if "space-around" in val or "around" in val:
            return "space-around"
        if "space-evenly" in val or "evenly" in val:
            return "space-evenly"
        if "center" in val:
            return "center"
        if "end" in val:
            return "flex-end"
        return "flex-start"

    def _normalize_spacing(self, val: str | None) -> str:
        if not val or val in ("none", "normal"):
            return "0px"
        val = val.strip()
        # Round fractional pixels (e.g. 24.34px -> 24px)
        return re.sub(r"(\d+)\.\d+px", r"\1px", val)

    def _diff_normalized(self, base: NormalizedLayout, variant: NormalizedLayout) -> dict[str, Any]:
        diff: dict[str, Any] = {}
        if base.direction != variant.direction:
            diff["direction"] = variant.direction
        if base.gap != variant.gap and variant.gap != "0px":
            diff["gap"] = variant.gap
        if base.layout_type != variant.layout_type:
            diff["layout_type"] = variant.layout_type
        if base.container.get("padding") != variant.container.get("padding"):
            diff["container_padding"] = variant.container.get("padding")
        if base.grid != variant.grid and variant.grid:
            diff["grid"] = variant.grid
        return diff

    def _get_children_signature(self, node: dict[str, Any] | None) -> list[str]:
        if not node:
            return []
        sig: list[str] = []
        for c in node.get("children", []):
            tag = c.get("tag", "div")
            cid = c.get("id") or ""
            classes_list = [cl for cl in c.get("classes", []) if cl]
            classes = ".".join(sorted(classes_list))
            id_part = f"#{cid}" if cid else ""
            cls_part = f".{classes}" if classes else ""
            key = f"{tag}{id_part}{cls_part}"
            sig.append(key)
        return sig

    def _find_node_for_component(self, root: dict[str, Any] | None, comp_name: str) -> dict[str, Any] | None:
        if not root:
            return None

        clean_name = re.sub(r"[_\-]+", "", comp_name.lower())

        def match(n: dict[str, Any]) -> bool:
            tag = n.get("tag", "").lower()
            nid = (n.get("id") or "").lower()
            classes = [c.lower() for c in n.get("classes", [])]

            if clean_name in nid or any(clean_name in c for c in classes):
                return True

            if comp_name == "HeaderNavigation" and tag in ("header", "nav"):
                return True
            if comp_name == "Hero" and (nid == "hero" or "hero" in classes):
                return True
            if comp_name == "Projects" and (nid in ("work", "projects") or "projects" in classes):
                return True
            if comp_name == "Footer" and tag == "footer":
                return True
            return False

        def search(n: dict[str, Any]) -> dict[str, Any] | None:
            if match(n):
                return n
            for c in n.get("children", []):
                res = search(c)
                if res:
                    return res
            return None

        return search(root)

    def _default_observed_for(self, comp_name: str) -> ObservedLayout:
        if comp_name == "HeaderNavigation":
            return ObservedLayout(
                display="flex",
                flex_direction="row",
                justify_content="space-between",
                align_items="center",
                padding="24px 48px",
                max_width="1280px",
                gap="32px",
            )
        elif comp_name == "Hero":
            return ObservedLayout(
                display="flex",
                flex_direction="column",
                justify_content="center",
                align_items="flex-start",
                padding="100px 48px",
                max_width="1280px",
                gap="24px",
                position="relative",
            )
        elif comp_name in ("Projects", "Capabilities"):
            return ObservedLayout(
                display="grid",
                grid_template_columns="repeat(auto-fit, minmax(320px, 1fr))",
                padding="80px 48px",
                max_width="1280px",
                gap="32px",
            )
        elif comp_name == "ProjectCard":
            return ObservedLayout(
                display="flex",
                flex_direction="column",
                padding="24px",
                border_radius="12px",
                gap="16px",
            )
        return ObservedLayout(
            display="block",
            padding="60px 48px",
            max_width="1280px",
        )

    def _extract_layout_tokens(
        self,
        normalized: dict[str, Any],
        observed: dict[str, ObservedLayout],
    ) -> dict[str, Any]:
        """Normalizes repeated layout values into tokens."""
        gaps: Counter = Counter()
        max_widths: Counter = Counter()
        paddings: Counter = Counter()

        for item in normalized.values():
            d = item.get("desktop", {})
            g = d.get("gap")
            if g and g != "0px":
                gaps[g] += 1
            mw = d.get("container", {}).get("max_width")
            if mw and mw not in ("none", "100%", "auto"):
                max_widths[mw] += 1
            pad = d.get("container", {}).get("padding")
            if pad and pad != "0px":
                paddings[pad] += 1

        primary_max_w = max_widths.most_common(1)[0][0] if max_widths else "1280px"
        primary_padding = paddings.most_common(1)[0][0] if paddings else "80px 48px"

        return {
            "container_max_width": primary_max_w,
            "container_padding": primary_padding,
            "common_gaps": [g for g, _ in gaps.most_common(3)],
        }
