from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from webextractor.generator.dom_emitter import DomToJsxEmitter


class ReactProjectGenerator:
    """
    Generate a maintainable React/Next.js project from Site IR.

    The generator only uses information available in the Site IR.
    It does not claim to reproduce hidden source code.
    """

    def __init__(
        self,
        site_ir: dict[str, Any] | Any,
        output_dir: str | Path,
    ):
        if hasattr(site_ir, "to_dict"):
            self.ir = site_ir.to_dict()
        elif hasattr(site_ir, "model_dump"):
            self.ir = site_ir.model_dump()
        elif isinstance(site_ir, dict):
            self.ir = site_ir
        else:
            self.ir = dict(site_ir)

        self.output = Path(output_dir)
        animations = self.ir.get("animations", {})
        appear_animations = animations.get("appear_animations", {})
        motion_triggers = animations.get("motion_triggers", [])
        motion_targets = set(appear_animations.keys())
        for mt in motion_triggers:
            sel = mt.get("target_selector")
            if sel:
                motion_targets.add(sel.lstrip(".#"))

        self.emitter = DomToJsxEmitter(
            component_tree=self.ir.get("components"),
            asset_bindings=self.ir.get("asset_bindings", []),
            motion_targets=motion_targets,
        )


    def generate(self) -> Path:
        self._create_structure()
        self._write_package()
        self._write_tsconfig()
        self._write_next_config()
        self._write_layout()
        self._write_tokens()
        self._write_global_styles()
        self._write_components()
        self._write_pages()
        self._write_not_found_page()
        self._write_data()
        self._write_analysis()

        return self.output

    # ---------------------------------------------------------
    # Structure
    # ---------------------------------------------------------

    def _create_structure(self):
        directories = [
            "app",
            "components",
            "data",
            "lib",
            "public",
            "public/images",
            "public/videos",
            "public/fonts",
            "styles",
            "analysis",
        ]

        for directory in directories:
            (self.output / directory).mkdir(
                parents=True,
                exist_ok=True,
            )

    # ---------------------------------------------------------
    # Package
    # ---------------------------------------------------------

    def _write_package(self):
        package = {
            "name": self._project_name(),
            "version": "1.0.0",
            "private": True,
            "scripts": {
                "dev": "next dev",
                "build": "next build",
                "start": "next start",
                "lint": "next lint",
            },
            "dependencies": {
                "next": "^15.1.0",
                "react": "^19.0.0",
                "react-dom": "^19.0.0",
            },
            "devDependencies": {
                "@types/node": "^22.0.0",
                "@types/react": "^19.0.0",
                "@types/react-dom": "^19.0.0",
                "typescript": "^5.7.0",
            },
        }

        self._json(
            "package.json",
            package,
        )

    # ---------------------------------------------------------
    # TypeScript
    # ---------------------------------------------------------

    def _write_tsconfig(self):
        self._json(
            "tsconfig.json",
            {
                "compilerOptions": {
                    "target": "ES2017",
                    "lib": [
                        "dom",
                        "dom.iterable",
                        "esnext",
                    ],
                    "allowJs": True,
                    "skipLibCheck": True,
                    "strict": True,
                    "noEmit": True,
                    "esModuleInterop": True,
                    "module": "esnext",
                    "moduleResolution": "bundler",
                    "resolveJsonModule": True,
                    "isolatedModules": True,
                    "jsx": "preserve",
                    "incremental": True,
                    "plugins": [
                        {
                            "name": "next"
                        }
                    ],
                    "paths": {
                        "@/*": ["./*"]
                    }
                },
                "include": [
                    "next-env.d.ts",
                    ".next/types/**/*.ts",
                    "**/*.ts",
                    "**/*.tsx",
                ],
                "exclude": [
                    "node_modules"
                ],
            },
        )


    def _write_next_config(self):
        self._text(
            "next.config.ts",
            """\
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
""",
        )

    # ---------------------------------------------------------
    # Layout
    # ---------------------------------------------------------

    def _write_layout(self):
        title = (
            self.ir
            .get("metadata", {})
            .get("title")
            or "Reconstructed Website"
        )
        animations = self.ir.get("animations", {})
        appear_animations = animations.get("appear_animations", {})
        interactions = self.ir.get("interactions", [])
        has_cursor = animations.get("has_cursor", False) or any(i.get("category") == "cursor" for i in interactions)
        has_route_transitions = any(i.get("category") == "route_transition" for i in interactions)

        layout_imports = [
            'import "../styles/tokens.css";',
            'import "./globals.css";',
            'import MotionRuntime from "../components/MotionRuntime";',
            'import FramerAppearRuntime from "../components/FramerAppearRuntime";',
        ]
        layout_elements = [
            "        {children}",
            "        <MotionRuntime animations={ANIMATIONS} />",
        ]

        if interactions:
            layout_imports.append('import InteractionRuntime from "../components/InteractionRuntime";')
            layout_elements.append("        <InteractionRuntime interactions={INTERACTIONS} />")

        if has_route_transitions:
            layout_imports.append('import RouteTransition from "../components/RouteTransition";')
            layout_elements.append("        <RouteTransition />")

        if has_cursor:
            layout_imports.append('import CursorRuntime, { CursorFollower } from "../components/CursorRuntime";')
            layout_elements.append("        <CursorRuntime />")

        imports_str = "\n".join(layout_imports)
        elements_str = "\n".join(layout_elements)
        constants_str = f"const ANIMATIONS: any = {json.dumps(animations)};\n"
        if interactions:
            constants_str += f"const INTERACTIONS: any = {json.dumps(interactions)};\n"

        self._text(
            "app/layout.tsx",
            f"""\
{imports_str}

{constants_str}
export const metadata = {{
  title: {json.dumps(title)},
}};

export default function RootLayout({{
  children,
}}: Readonly<{{
  children: React.ReactNode;
}}>) {{
  return (
    <html lang="en">
      <body>
{elements_str}
      </body>
    </html>
  );
}}
""",
        )

    # ---------------------------------------------------------
    # Tokens
    # ---------------------------------------------------------

    def _write_tokens(self):
        design = self.ir.get(
            "design_system",
            {},
        )

        colors = design.get(
            "colors",
            {},
        )

        radii = design.get(
            "radii",
            {},
        )

        typo_ir = self.ir.get("typography") or {}
        font_families = typo_ir.get("font_families", [])
        roles = typo_ir.get("roles", {})
        responsive = typo_ir.get("responsive", {})

        # 1. Local @font-face declarations
        font_face_blocks = []
        for font in font_families:
            if font.get("source") == "local" and font.get("local_path"):
                local_path = str(font["local_path"])
                if local_path.startswith("public/"):
                    url_path = "/" + local_path[len("public/"):].lstrip("/")
                elif not local_path.startswith("/"):
                    url_path = "/" + local_path
                else:
                    url_path = local_path

                weights = font.get("weights") or [400]
                styles = font.get("styles") or ["normal"]
                for style in styles:
                    for weight in weights:
                        font_face_blocks.append(
                            f"@font-face {{\n"
                            f"  font-family: '{font['name']}';\n"
                            f"  src: url('{url_path}');\n"
                            f"  font-weight: {weight};\n"
                            f"  font-style: {style};\n"
                            f"  font-display: swap;\n"
                            f"}}"
                        )

        lines = [":root {"]

        # Colors
        for name, value in colors.items():
            lines.append(f"  --color-{self._css_name(name)}: {value};")

        # Radii
        for name, value in radii.items():
            lines.append(f"  --radius-{self._css_name(name)}: {value};")

        # Layout Tokens (Container, Spacing, Gaps)
        layout_ir = self.ir.get("layout", {})
        layout_tokens = layout_ir.get("tokens", {})
        container_max_w = layout_tokens.get("container_max_width", "1280px")
        container_padding = layout_tokens.get("container_padding", "80px 48px")
        lines.append(f"  --container-max-width: {container_max_w};")
        lines.append(f"  --container-padding: {container_padding};")

        common_gaps = layout_tokens.get("common_gaps", ["16px", "24px", "32px"])
        gap_labels = ["sm", "md", "lg", "xl"]
        for idx, g in enumerate(common_gaps[:4]):
            lbl = gap_labels[idx] if idx < len(gap_labels) else f"gap-{idx}"
            lines.append(f"  --layout-gap-{lbl}: {g};")

        # Legacy design_system sizes
        legacy_typography = design.get("typography", {})
        legacy_sizes = legacy_typography.get("sizes", {})
        for name, value in legacy_sizes.items():
            lines.append(f"  --font-size-{self._css_name(name)}: {value};")

        # Helper to format font family stack
        def build_font_stack(primary: str, fallbacks: list[str]) -> str:
            if not primary:
                return ", ".join(fallbacks) if fallbacks else "sans-serif"
            if "," in primary:
                return primary
            quoted_primary = f"'{primary}'" if " " in primary and not (primary.startswith("'") or primary.startswith('"')) else primary
            stack = [quoted_primary]
            for fb in fallbacks:
                clean_fb = fb.strip().strip("'").strip('"')
                if clean_fb and clean_fb.lower() != primary.lower():
                    quoted_fb = f"'{clean_fb}'" if " " in clean_fb and not (clean_fb.startswith("'") or clean_fb.startswith('"') or clean_fb.startswith("-")) else clean_fb
                    stack.append(quoted_fb)
            return ", ".join(stack)

        # Font Families: --font-display, --font-body, --font-mono
        display_stack = None
        if roles.get("display") and roles["display"].get("font_family"):
            fam_name = roles["display"]["font_family"]
            matched_font = next((f for f in font_families if f.get("name") == fam_name), None)
            fallbacks = matched_font.get("fallbacks", ["sans-serif"]) if matched_font else ["sans-serif"]
            display_stack = build_font_stack(fam_name, fallbacks)
        elif legacy_typography.get("display", {}).get("family"):
            display_stack = legacy_typography["display"]["family"]
        elif font_families:
            display_stack = build_font_stack(font_families[0]["name"], font_families[0].get("fallbacks", ["sans-serif"]))
        else:
            display_stack = "system-ui, -apple-system, sans-serif"

        body_stack = None
        if roles.get("body") and roles["body"].get("font_family"):
            fam_name = roles["body"]["font_family"]
            matched_font = next((f for f in font_families if f.get("name") == fam_name), None)
            fallbacks = matched_font.get("fallbacks", ["system-ui", "-apple-system", "sans-serif"]) if matched_font else ["system-ui", "-apple-system", "sans-serif"]
            body_stack = build_font_stack(fam_name, fallbacks)
        elif legacy_typography.get("body", {}).get("family"):
            body_stack = legacy_typography["body"]["family"]
        elif len(font_families) > 1:
            body_stack = build_font_stack(font_families[1]["name"], font_families[1].get("fallbacks", ["sans-serif"]))
        elif font_families:
            body_stack = build_font_stack(font_families[0]["name"], font_families[0].get("fallbacks", ["sans-serif"]))
        else:
            body_stack = "system-ui, -apple-system, sans-serif"

        mono_stack = None
        if roles.get("mono") and roles["mono"].get("font_family") and roles["mono"]["font_family"] not in ("ui-monospace, monospace", "monospace"):
            fam_name = roles["mono"]["font_family"]
            matched_font = next((f for f in font_families if f.get("name") == fam_name), None)
            fallbacks = matched_font.get("fallbacks", ["monospace"]) if matched_font else ["monospace"]
            mono_stack = build_font_stack(fam_name, fallbacks)
        else:
            mono_stack = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"

        lines.append(f"  --font-display: {display_stack};")
        lines.append(f"  --font-body: {body_stack};")
        lines.append(f"  --font-mono: {mono_stack};")

        # Typography role tokens
        effective_roles = dict(roles)
        if not effective_roles:
            effective_roles = {
                "hero": {"font_size": "72px", "font_weight": "800", "line_height": "1.05"},
                "heading": {"font_size": "40px", "font_weight": "700", "line_height": "1.15"},
                "subheading": {"font_size": "24px", "font_weight": "600", "line_height": "1.25"},
                "body": {"font_size": "16px", "font_weight": "400", "line_height": "1.6"},
                "caption": {"font_size": "13px", "font_weight": "400", "line_height": "1.5"},
                "label": {"font_size": "12px", "font_weight": "600", "line_height": "1.2", "letter_spacing": "0.12em", "text_transform": "uppercase"},
                "navigation": {"font_size": "14px", "font_weight": "500", "line_height": "1.4"},
                "button": {"font_size": "15px", "font_weight": "600", "line_height": "1.2"},
                "mono": {"font_size": "14px", "font_weight": "400", "line_height": "1.5"},
            }

        for role_name, r_def in sorted(effective_roles.items()):
            role_slug = self._css_name(role_name)
            if r_def.get("font_size"):
                lines.append(f"  --type-{role_slug}-size: {r_def['font_size']};")
            if r_def.get("font_weight"):
                lines.append(f"  --type-{role_slug}-weight: {r_def['font_weight']};")
            if r_def.get("line_height"):
                lines.append(f"  --type-{role_slug}-line-height: {r_def['line_height']};")
            if r_def.get("letter_spacing") and r_def["letter_spacing"] != "normal":
                lines.append(f"  --type-{role_slug}-letter-spacing: {r_def['letter_spacing']};")
            elif role_name == "label":
                lines.append(f"  --type-{role_slug}-letter-spacing: {r_def.get('letter_spacing', '0.12em')};")
            if r_def.get("text_transform") and r_def["text_transform"] != "none":
                lines.append(f"  --type-{role_slug}-transform: {r_def['text_transform']};")
            elif role_name == "label":
                lines.append(f"  --type-{role_slug}-transform: {r_def.get('text_transform', 'uppercase')};")

        lines.append("}")

        # Responsive Overrides (Mobile)
        mobile_overrides = responsive.get("mobile", {})
        if mobile_overrides:
            lines.append("")
            lines.append("@media (max-width: 768px) {")
            lines.append("  :root {")
            for role_name, diffs in sorted(mobile_overrides.items()):
                role_slug = self._css_name(role_name)
                if diffs.get("font_size"):
                    lines.append(f"    --type-{role_slug}-size: {diffs['font_size']};")
                if diffs.get("line_height"):
                    lines.append(f"    --type-{role_slug}-line-height: {diffs['line_height']};")
                if diffs.get("letter_spacing"):
                    lines.append(f"    --type-{role_slug}-letter-spacing: {diffs['letter_spacing']};")
            lines.append("  }")
            lines.append("}")

        full_css = ""
        if font_face_blocks:
            full_css += "\n\n".join(font_face_blocks) + "\n\n"
        full_css += "\n".join(lines) + "\n"

        self._text(
            "styles/tokens.css",
            full_css,
        )

    # ---------------------------------------------------------
    # Global CSS & Responsive Component Styles
    # ---------------------------------------------------------

    def _write_global_styles(self):
        component_styles = self.ir.get("component_styles", {})
        layout_ir = self.ir.get("layout", {})
        normalized_layouts = layout_ir.get("normalized", {})

        all_comp_names = sorted(set(list(component_styles.keys()) + list(normalized_layouts.keys())))

        style_rules = []
        tablet_media_rules = []
        mobile_media_rules = []

        for comp_name in all_comp_names:
            class_name = self._class_name(comp_name)
            styles = component_styles.get(comp_name, {})
            norm = normalized_layouts.get(comp_name, {})
            d_norm = norm.get("desktop", {})
            r_norm = norm.get("responsive", {})

            # 1. Desktop Properties
            desktop_props: dict[str, str] = {}

            # Apply normalized structural layout
            l_type = d_norm.get("layout_type")
            if l_type == "flex":
                desktop_props["display"] = "flex"
                desktop_props["flex-direction"] = d_norm.get("direction", "column")
                desktop_props["align-items"] = d_norm.get("align", "stretch")
                desktop_props["justify-content"] = d_norm.get("justify", "flex-start")
                desktop_props["flex-wrap"] = d_norm.get("wrap", "nowrap")
                if d_norm.get("gap") and d_norm["gap"] != "0px":
                    desktop_props["gap"] = d_norm["gap"]
            elif l_type == "grid":
                desktop_props["display"] = "grid"
                grid = d_norm.get("grid", {})
                desktop_props["grid-template-columns"] = grid.get("columns", "repeat(auto-fit, minmax(320px, 1fr))")
                if grid.get("gap") and grid["gap"] != "0px":
                    desktop_props["gap"] = grid["gap"]

            container = d_norm.get("container", {})
            if container.get("max_width") and container["max_width"] != "none":
                desktop_props["max-width"] = container["max_width"]
            if container.get("is_centered"):
                desktop_props["margin"] = container.get("margin", "0 auto")
            if container.get("padding") and container["padding"] != "0px":
                desktop_props["padding"] = container["padding"]

            pos = d_norm.get("positioning", {})
            if pos.get("position") and pos["position"] != "static":
                desktop_props["position"] = pos["position"]
            if pos.get("z_index") and pos["z_index"] not in ("auto", None):
                desktop_props["z-index"] = str(pos["z_index"])

            vis = d_norm.get("visual", {})
            if vis.get("overflow") and vis["overflow"] != "visible":
                desktop_props["overflow"] = vis["overflow"]
            if vis.get("border_radius") and vis["border_radius"] != "0px":
                desktop_props["border-radius"] = vis["border_radius"]

            # Merge observed component_styles
            for prop, val in styles.get("desktop", {}).items():
                desktop_props[self._to_kebab(prop)] = str(val)

            if desktop_props:
                css_lines = [f"  {k}: {v};" for k, v in sorted(desktop_props.items())]
                style_rules.append(f".{class_name} {{\n" + "\n".join(css_lines) + "\n}")

            # 2. Tablet Responsive Rules
            t_diff = r_norm.get("tablet", {})
            if t_diff:
                t_props: dict[str, str] = {}
                if t_diff.get("direction"):
                    t_props["flex-direction"] = t_diff["direction"]
                if t_diff.get("gap"):
                    t_props["gap"] = t_diff["gap"]
                if t_diff.get("container_padding"):
                    t_props["padding"] = t_diff["container_padding"]
                if t_props:
                    t_lines = [f"    {k}: {v};" for k, v in sorted(t_props.items())]
                    tablet_media_rules.append(f"  .{class_name} {{\n" + "\n".join(t_lines) + "\n  }")

            # 3. Mobile Responsive Rules
            mobile_props: dict[str, str] = {}
            m_diff = r_norm.get("mobile", {})
            if m_diff.get("direction"):
                mobile_props["flex-direction"] = m_diff["direction"]
            if m_diff.get("gap"):
                mobile_props["gap"] = m_diff["gap"]
            if m_diff.get("container_padding"):
                mobile_props["padding"] = m_diff["container_padding"]
            if m_diff.get("layout_type"):
                mobile_props["display"] = m_diff["layout_type"]

            for prop, val in styles.get("mobile", {}).items():
                mobile_props[self._to_kebab(prop)] = str(val)

            if mobile_props:
                m_lines = [f"    {k}: {v};" for k, v in sorted(mobile_props.items())]
                mobile_media_rules.append(f"  .{class_name} {{\n" + "\n".join(m_lines) + "\n  }")

        media_block = ""
        if tablet_media_rules:
            media_block += "\n@media (max-width: 1024px) {\n" + "\n\n".join(tablet_media_rules) + "\n}\n"
        if mobile_media_rules:
            media_block += "\n@media (max-width: 768px) {\n" + "\n\n".join(mobile_media_rules) + "\n}\n"


        # Process authoritative responsive rules from SiteIR
        responsive_rules = self.ir.get("responsive_rules", [])
        ir_media_blocks: dict[str, list[str]] = {}

        for r in responsive_rules:
            mq = r.get("media_query") or "@media (max-width: 768px)"
            sel = r.get("selector")
            if not sel or not r.get("diffs"):
                continue

            if "_" in sel and not (sel.startswith(".") or sel.startswith("#") or sel.startswith("[")):
                parts = sel.split("_")
                if len(parts) >= 3 and parts[2].strip():
                    sel = "." + ".".join(parts[2].strip().split())
                elif parts[0]:
                    sel = parts[0]

            prop_lines = []
            bp = r.get("breakpoint", "")
            for prop, val_data in r["diffs"].items():
                kebab_prop = re.sub(r"([A-Z])", r"-\1", prop).lower()
                val = None
                if isinstance(val_data, dict):
                    val = val_data.get(bp) or val_data.get("target") or val_data.get("mobile") or next((v for k, v in val_data.items() if k != "desktop"), None)
                else:
                    val = val_data
                if val:
                    prop_lines.append(f"    {kebab_prop}: {val} !important;")

            if prop_lines:
                ir_media_blocks.setdefault(mq, []).append(f"  {sel} {{\n" + "\n".join(prop_lines) + "\n  }")

        if "@media (max-width: 768px)" not in ir_media_blocks:
            ir_media_blocks["@media (max-width: 768px)"] = []
        ir_media_blocks["@media (max-width: 768px)"].insert(0, """  html, body {
    max-width: 100vw;
  }
  .wx-container {
    padding: 0 16px;
    max-width: 100%;
  }""")

        for mq, rules in sorted(ir_media_blocks.items()):
            media_block += f"\n{mq} {{\n" + "\n\n".join(rules) + "\n}\n"

        # Source-extracted rules (font-faces, relevant classes, media rules, keyframes)
        source_rules = self.ir.get("component_styles", {}).get("source_rules", {})
        font_faces = source_rules.get("font_faces", [])
        class_rules = source_rules.get("class_rules", [])
        source_media_rules = source_rules.get("media_rules", [])
        keyframes = source_rules.get("keyframes", [])

        font_face_block = ("\n\n".join(font_faces) + "\n\n") if font_faces else ""
        source_class_block = ("\n\n/* Source Extracted Element Styles */\n" + "\n\n".join(class_rules)) if class_rules else ""
        source_keyframes_block = ("\n\n/* Source Extracted Keyframes */\n" + "\n\n".join(keyframes)) if keyframes else ""
        source_media_block = ("\n\n/* Source Extracted Responsive Rules */\n" + "\n\n".join(source_media_rules)) if source_media_rules else ""

        # Preserved element transitions (cubic-bezier / steps / explicit durations)
        element_transitions = self.ir.get("animations", {}).get("element_transitions", {})
        element_trans_block = ""
        if element_transitions:
            trans_rules = []
            site_tf = self.ir.get("animations", {}).get("timing_function") or self.ir.get("animations", {}).get("default_timing_function") or self.ir.get("animations", {}).get("default_easing")
            site_dur = self.ir.get("animations", {}).get("default_transition_duration", 0.3)
            for sel, t_cfg in element_transitions.items():
                tf = t_cfg.get("timing_function") or t_cfg.get("easing") or t_cfg.get("ease") or site_tf
                dur = t_cfg.get("duration") if t_cfg.get("duration") is not None else site_dur
                if tf:
                    trans_rules.append(f"{sel} {{\n  transition: all {dur}s {tf} !important;\n}}")
            if trans_rules:
                element_trans_block = "\n\n/* Element Transitions (Preserved Curves) */\n" + "\n\n".join(trans_rules)

        css_content = font_face_block + """\
* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  background: var(--color-background, #080808);
  color: var(--color-foreground, #f5f5f5);
  font-family: var(--font-body, system-ui, -apple-system, sans-serif);
}

img,
video {
  display: block;
  max-width: 100%;
}

button,
a {
  font: inherit;
}

a {
  color: inherit;
  text-decoration: none;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-display, var(--font-body, system-ui, sans-serif));
}

code, pre, kbd {
  font-family: var(--font-mono, ui-monospace, monospace);
}

/* Custom Cursor Native Suppression */
body.has-custom-cursor,
body.has-custom-cursor * {
  cursor: none !important;
}

/* Responsive fallback for single-variant SSR sections: prevent desktop-only capture from vanishing on viewports < 1440px */
.ssr-variant:only-child,
.ssr-variant:only-of-type {
  display: block !important;
}

/* Component Classes */
""" + "\n\n".join(style_rules) + source_class_block + source_keyframes_block + element_trans_block + media_block + source_media_block

        # Append responsive fallback after media queries to ensure single-variant SSR components remain visible across all viewports
        css_content += """
/* Responsive fallback for single-variant SSR sections: prevent desktop-only capture from vanishing on viewports < 1440px */
.ssr-variant:only-child,
.ssr-variant:only-of-type,
div > .ssr-variant:only-child {
  display: block !important;
}
"""

        self._text(
            "app/globals.css",
            css_content + "\n",
        )

    # ---------------------------------------------------------
    # Components
    # ---------------------------------------------------------

    def _write_components(self):
        # 1. Page-level components from SiteIR pages
        pages = self.ir.get("pages", [])
        page_components = []
        if pages:
            page_components = pages[0].get("components", [])

        # No hardcoded fallback — only emit what was actually found in DOM
        page_comp_names = set()
        for item in page_components:
            name = item.get("name") if isinstance(item, dict) else str(item)
            if name:
                page_comp_names.add(name)
                self._write_page_component(name)

        # 2. Reusable Item Components (discovered from DOM clustering)
        reusable = self.ir.get("reusable_components", [])
        if isinstance(reusable, dict):
            reusable = list(reusable.values())

        reusable_names = set()
        for item in reusable:
            name = item.get("name") if isinstance(item, dict) else str(item)
            if name:
                cleaned = self._component_name({"name": name})
                reusable_names.add(cleaned)

        # Add standard reusable components only if their parent sections exist in page_components
        page_comp_names_lower = {n.lower() for n in page_comp_names}
        data_ir = self.ir.get("data", {})
        if data_ir.get("projects") or any("project" in n for n in page_comp_names_lower):
            reusable_names.add("ProjectCard")
        if data_ir.get("capabilities") or any("capabil" in n or "service" in n for n in page_comp_names_lower):
            reusable_names.add("CapabilityItem")
        if data_ir.get("journey") or any("journey" in n or "experience" in n for n in page_comp_names_lower):
            reusable_names.add("JourneyItem")
        if data_ir.get("toolkit") or any("tool" in n or "skill" in n for n in page_comp_names_lower):
            reusable_names.add("ToolkitItem")
        # NavItem is always useful
        reusable_names.add("NavItem")

        for name in reusable_names:
            if name not in page_comp_names:
                self._write_reusable_component(name)

        # 3. Interactive Runtime Components
        self._write_runtime_components()

    def _write_page_component(self, name: str):
        class_name = self._class_name(name)
        node = self.emitter.find_node_for_component(name)

        if node:
            # Emit authentic DOM content from captured snapshot
            emitted_jsx = self.emitter.emit_jsx(
                node,
                depth=2,
                root_classes=f"{class_name} ${{className}}".strip(),
                root_id=name.lower() if node.get("tag") in ("section", "article") else None,
            )
            clock_import = 'import LiveClock from "./LiveClock";\n' if "<LiveClock" in emitted_jsx else ""
            code = f"""import React from "react";
{clock_import}
type {name}Props = {{
  className?: string;
}};

export default function {name}({{
  className = "",
}}: {name}Props) {{
  return (
{emitted_jsx.rstrip()}
  );
}}
"""
        else:
            # Check if any asset bindings apply to this component
            comp_bindings = [
                b for b in self.ir.get("asset_bindings", [])
                if b.get("component") == name
            ]
            inner_elements = []
            for b in comp_bindings:
                lp = b.get("local_path") or b.get("source_url")
                if not lp:
                    continue
                b_type = b.get("type", "")
                if b_type == "video" or b.get("role") == "video":
                    inner_elements.append(f'      <video src="{lp}" autoPlay loop muted playsInline style={{{{ width: "100%", height: "auto" }}}} />')
                elif b_type == "image" or b.get("role") in ("logo", "image"):
                    inner_elements.append(f'      <img src="{lp}" alt="{name}" style={{{{ maxWidth: "100%", height: "auto" }}}} />')

            if self.ir.get("typography") and name == "Hero" and not inner_elements:
                inner_content = """      <h1 style={{ fontFamily: "var(--font-display)", fontSize: "var(--type-hero-size, 48px)" }}>
        Hero
      </h1>
      <p style={{ fontFamily: "var(--font-body)", fontSize: "var(--type-body-size, 16px)" }}>
        Hero description
      </p>"""
            elif self.ir.get("typography") and name == "Projects" and not inner_elements:
                inner_content = """      <h2 style={{ fontFamily: "var(--font-display)", fontSize: "var(--type-heading-size, 32px)" }}>
        Projects
      </h2>"""
            else:
                inner_content = "\n".join(inner_elements) if inner_elements else "      {children}"
            style_attr = ' style={{ fontFamily: "var(--font-display, inherit)" }}' if self.ir.get("typography") else ""

            code = f"""import React from "react";

type {name}Props = {{
  children?: React.ReactNode;
  className?: string;
}};

export default function {name}({{
  children,
  className = "",
}}: {name}Props) {{
  return (
    <section className={{`{class_name} ${{className}}`.trim()}}{style_attr}>
{inner_content}
    </section>
  );
}}
"""
        self._text(f"components/{name}.tsx", code)

    def _write_reusable_component(self, name: str):
        class_name = self._class_name(name)

        if name == "ProjectCard":
            code = f"""import React from "react";
import {{ Project }} from "../data/projects";

type ProjectCardProps = {{
  project: Project;
  className?: string;
}};

export default function ProjectCard({{
  project,
  className = "",
}}: ProjectCardProps) {{
  return (
    <article className={{"{class_name} " + className}}>
      {{project.image && (
        <div
          className="project-card-image"
          style={{{{
            width: "100%",
            height: "200px",
            overflow: "hidden",
            borderRadius: "10px",
            marginBottom: "16px",
          }}}}
        >
          <img
            src={{project.image}}
            alt={{project.title}}
            style={{{{ width: "100%", height: "100%", objectFit: "cover" }}}}
          />
        </div>
      )}}
      <h3 style={{{{ fontFamily: "var(--font-display)", fontSize: "var(--type-subheading-size, 24px)", fontWeight: "var(--type-subheading-weight, 600)", margin: "0 0 12px 0" }}}}>
        {{project.title}}
      </h3>
      {{project.description && (
        <p style={{{{ fontFamily: "var(--font-body)", fontSize: "var(--type-body-size, 14px)", lineHeight: "var(--type-body-line-height, 1.6)", opacity: 0.75, marginBottom: "20px" }}}}>
          {{project.description}}
        </p>
      )}}
      {{project.tags && project.tags.length > 0 && (
        <div style={{{{ display: "flex", gap: "8px", flexWrap: "wrap" }}}}>
          {{project.tags.map((tag, i) => (
            <span
              key={{i}}
              style={{{{
                fontFamily: "var(--font-body)",
                fontSize: "var(--type-caption-size, 12px)",
                padding: "4px 10px",
                borderRadius: "9999px",
                background: "rgba(255, 255, 255, 0.08)",
              }}}}
            >
              {{tag}}
            </span>
          ))}}
        </div>
      )}}
    </article>
  );
}}
"""

        elif name == "CapabilityItem":
            code = f"""import React from "react";

export type CapabilityItemProps = {{
  title?: string;
  description?: string;
  className?: string;
  children?: React.ReactNode;
}};

export default function CapabilityItem({{
  title,
  description,
  className = "",
  children,
}}: CapabilityItemProps) {{
  if (children) {{
    return <div className={{"{class_name} " + className}}>{{children}}</div>;
  }}

  return (
    <div className={{"{class_name} " + className}} style={{{{ background: "rgba(255, 255, 255, 0.03)", padding: "24px", borderRadius: "12px" }}}}>
      {{title && (
        <h3 style={{{{ fontFamily: "var(--font-display)", fontSize: "var(--type-subheading-size, 20px)", fontWeight: "var(--type-subheading-weight, 600)", marginBottom: "8px" }}}}>
          {{title}}
        </h3>
      )}}
      {{description && (
        <p style={{{{ fontFamily: "var(--font-body)", opacity: 0.7, fontSize: "var(--type-body-size, 15px)", lineHeight: "var(--type-body-line-height, 1.5)" }}}}>
          {{description}}
        </p>
      )}}
    </div>
  );
}}
"""
        elif name == "JourneyItem":
            code = f"""import React from "react";

export type JourneyItemProps = {{
  period?: string;
  role?: string;
  description?: string;
  className?: string;
  children?: React.ReactNode;
}};

export default function JourneyItem({{
  period,
  role,
  description,
  className = "",
  children,
}}: JourneyItemProps) {{
  if (children) {{
    return <div className={{"{class_name} " + className}}>{{children}}</div>;
  }}

  return (
    <div className={{"{class_name} " + className}}>
      {{period && (
        <span style={{{{ fontFamily: "var(--font-body)", fontSize: "var(--type-caption-size, 13px)", opacity: 0.5, textTransform: "uppercase", letterSpacing: "var(--type-label-letter-spacing, 0.1em)" }}}}>
          {{period}}
        </span>
      )}}
      {{role && (
        <h3 style={{{{ fontFamily: "var(--font-display)", fontSize: "var(--type-subheading-size, 20px)", fontWeight: "var(--type-subheading-weight, 600)", margin: "6px 0 8px 0" }}}}>
          {{role}}
        </h3>
      )}}
      {{description && (
        <p style={{{{ fontFamily: "var(--font-body)", opacity: 0.75, fontSize: "var(--type-body-size, 14px)", lineHeight: "var(--type-body-line-height, 1.6)" }}}}>
          {{description}}
        </p>
      )}}
    </div>
  );
}}
"""
        elif name == "ToolkitItem":
            code = f"""import React from "react";

export type ToolkitItemProps = {{
  name?: string;
  className?: string;
  children?: React.ReactNode;
}};

export default function ToolkitItem({{
  name,
  className = "",
  children,
}}: ToolkitItemProps) {{
  if (children) {{
    return <span className={{"{class_name} " + className}}>{{children}}</span>;
  }}

  return (
    <span
      className={{"{class_name} " + className}}
      style={{{{
        background: "rgba(255, 255, 255, 0.05)",
        border: "1px solid rgba(255, 255, 255, 0.1)",
        padding: "10px 18px",
        borderRadius: "8px",
        fontFamily: "var(--font-mono, monospace)",
        fontSize: "var(--type-caption-size, 14px)",
        fontWeight: 500,
      }}}}
    >
      {{name}}
    </span>
  );
}}
"""
        else:
            code = f"""import React from "react";

type {name}Props = {{
  children?: React.ReactNode;
  className?: string;
}};

export default function {name}({{
  children,
  className = "",
}}: {name}Props) {{
  return (
    <div className={{"{class_name} " + className}}>
      {{children}}
    </div>
  );
}}
"""
        self._text(f"components/{name}.tsx", code)

    def _write_runtime_components(self):
        # 1. MotionRuntime.tsx (Generic native browser animation runtime)
        self._text(
            "components/MotionRuntime.tsx",
            """\"use client\";

import { useEffect } from "react";

export interface MotionConfig {
  initial?: Record<string, any>;
  animate?: Record<string, any>;
  hover?: Record<string, any>;
  press?: Record<string, any>;
  transition?: Record<string, any>;
  variants?: Record<string, any>;
  trigger?: "mount" | "in_view" | "hover" | "scroll" | string;
  inView?: boolean;
  once?: boolean;
  threshold?: number;
  keyframes?: Array<Record<string, any>>;
  repeat?: number | "Infinity";
  continuous?: boolean;
  parallaxSpeed?: number;
  [key: string]: any;
}

export type AppearConfig = MotionConfig;

export interface MotionRuntimeProps {
  animations?: Record<string, any>;
}

export default function MotionRuntime({
  animations = {},
}: MotionRuntimeProps) {
  useEffect(() => {
    if (!animations || Object.keys(animations).length === 0) return;
    if (typeof window === "undefined") return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    // Normalization: animations can be a map of configs or an object containing appear_animations, motion_triggers, etc.
    const appearMap: Record<string, MotionConfig> = animations.appear_animations || (animations.initial ? {} : animations);
    const triggers: Array<Record<string, any>> = animations.motion_triggers || [];
    const parallaxList: string[] = animations.parallax_elements || [];

    const cleanupFns: Array<() => void> = [];

    // Helper: calculate transform string from config object
    function getTransform(val: Record<string, any>): string {
      const x = val.x !== undefined ? (typeof val.x === "number" ? `${val.x}px` : val.x) : "0px";
      const y = val.y !== undefined ? (typeof val.y === "number" ? `${val.y}px` : val.y) : "0px";
      const scale = val.scale !== undefined ? val.scale : 1;
      const rotate = val.rotate !== undefined ? (typeof val.rotate === "number" ? `${val.rotate}deg` : val.rotate) : "0deg";
      return `translate3d(${x}, ${y}, 0) scale(${scale}) rotate(${rotate})`;
    }

    // Helper: calculate duration from transition
    function getDuration(transition: Record<string, any>): number {
      if (transition.type === "spring") {
        const stiffness = transition.stiffness || 200;
        const damping = transition.damping || 40;
        return Math.max(600, Math.min(1800, (damping / (2 * Math.sqrt(stiffness))) * 1200 + 400));
      }
      return (transition.duration || 0.8) * 1000;
    }

    // Safe element finder: handles IDs starting with numbers and arbitrary strings without CSS selector errors
    const findTarget = (targetId: string): HTMLElement | null => {
      if (!targetId) return null;
      const byId = document.getElementById(targetId);
      if (byId) return byId;

      try {
        const el = document.querySelector(
          `[data-motion-id="${targetId}"], [data-framer-appear-id="${targetId}"], [id="${targetId}"]`
        );
        if (el instanceof HTMLElement) return el;
      } catch {}

      try {
        const escaped = typeof CSS !== "undefined" && CSS.escape ? CSS.escape(targetId) : targetId;
        const el = document.querySelector(`.motion-${escaped}`);
        if (el instanceof HTMLElement) return el;
      } catch {}

      return null;
    };

    const defaultTimingFunction = (animations && (animations.timing_function || animations.default_timing_function || animations.default_easing)) || "cubic-bezier(0.25, 0.1, 0.25, 1)";

    // 1. Process Appear / Motion Configs
    Object.entries(appearMap).forEach(([targetId, config]) => {
      const el = findTarget(targetId);
      if (!el) return;

      const initial = config.initial || {};
      const animate = config.animate || {};
      const hover = config.hover || {};
      const press = config.press || {};
      const transition = config.transition || {};

      const delayMs = (transition.delay || 0) * 1000;
      const durationMs = getDuration(transition);
      const isContinuous = config.continuous || config.repeat === "Infinity" || config.repeat === Infinity;

      const initTransform = getTransform(initial);
      const targetTransform = getTransform(animate);
      const initOpacity = initial.opacity !== undefined ? initial.opacity : 1;
      const targetOpacity = animate.opacity !== undefined ? animate.opacity : 1;

      const runEntranceAnimation = () => {
        try {
          const keyframes = config.keyframes || [
            { opacity: initOpacity, transform: initTransform },
            { opacity: targetOpacity, transform: targetTransform },
          ];
          const easing = transition.timing_function || transition.easing || transition.ease || defaultTimingFunction || (transition.type === "spring" ? "cubic-bezier(0.16, 1, 0.3, 1)" : "cubic-bezier(0.25, 0.1, 0.25, 1)");
          const anim = el.animate(keyframes, {
            duration: durationMs,
            delay: delayMs,
            easing: easing,
            fill: "both",
            iterations: isContinuous ? Infinity : 1,
            direction: isContinuous ? "alternate" : "normal",
          });
          return anim;
        } catch (err) {
          el.style.transform = targetTransform;
          el.style.opacity = `${targetOpacity}`;
        }
      };

      // In-View Trigger vs Mount Trigger
      const isInView = config.trigger === "in_view" || config.inView;
      if (isInView && typeof IntersectionObserver !== "undefined") {
        const once = config.once !== false;
        const observer = new IntersectionObserver(
          (entries) => {
            entries.forEach((entry) => {
              if (entry.isIntersecting) {
                runEntranceAnimation();
                if (once) observer.unobserve(el);
              } else if (!once) {
                el.style.opacity = `${initOpacity}`;
                el.style.transform = initTransform;
              }
            });
          },
          { threshold: config.threshold || 0.15 }
        );
        observer.observe(el);
        cleanupFns.push(() => observer.disconnect());
      } else {
        runEntranceAnimation();
      }

      // Hover interaction variant
      if (Object.keys(hover).length > 0) {
        const hoverTransform = getTransform(hover);
        const hoverOpacity = hover.opacity !== undefined ? hover.opacity : targetOpacity;
        const hoverEasing = hover.transition?.timing_function || hover.transition?.easing || defaultTimingFunction;

        const onPointerEnter = () => {
          el.animate(
            [
              { opacity: targetOpacity, transform: targetTransform },
              { opacity: hoverOpacity, transform: hoverTransform },
            ],
            { duration: 250, fill: "forwards", easing: hoverEasing }
          );
        };
        const onPointerLeave = () => {
          el.animate(
            [
              { opacity: hoverOpacity, transform: hoverTransform },
              { opacity: targetOpacity, transform: targetTransform },
            ],
            { duration: 300, fill: "forwards", easing: hoverEasing }
          );
        };
        el.addEventListener("pointerenter", onPointerEnter);
        el.addEventListener("pointerleave", onPointerLeave);
        cleanupFns.push(() => {
          el.removeEventListener("pointerenter", onPointerEnter);
          el.removeEventListener("pointerleave", onPointerLeave);
        });
      }

      // Press / tap interaction variant
      if (Object.keys(press).length > 0) {
        const pressTransform = getTransform(press);
        const pressEasing = press.transition?.timing_function || press.transition?.easing || defaultTimingFunction;
        const onPointerDown = () => {
          el.animate(
            [{ transform: targetTransform }, { transform: pressTransform }],
            { duration: 150, fill: "forwards", easing: pressEasing }
          );
        };
        const onPointerUp = () => {
          el.animate(
            [{ transform: pressTransform }, { transform: targetTransform }],
            { duration: 200, fill: "forwards", easing: pressEasing }
          );
        };
        el.addEventListener("pointerdown", onPointerDown);
        el.addEventListener("pointerup", onPointerUp);
        el.addEventListener("pointercancel", onPointerUp);
        cleanupFns.push(() => {
          el.removeEventListener("pointerdown", onPointerDown);
          el.removeEventListener("pointerup", onPointerUp);
          el.removeEventListener("pointercancel", onPointerUp);
        });
      }
    });

    // 2. Parallax / Scroll-Linked Elements
    const parallaxElements: HTMLElement[] = [];
    parallaxList.forEach((sel) => {
      try {
        document.querySelectorAll(sel).forEach((node) => {
          if (node instanceof HTMLElement) parallaxElements.push(node);
        });
      } catch {}
    });
    try {
      document.querySelectorAll("[data-parallax]").forEach((node) => {
        if (node instanceof HTMLElement && !parallaxElements.includes(node)) {
          parallaxElements.push(node);
        }
      });
    } catch {}

    if (parallaxElements.length > 0) {
      let ticking = false;
      const onScroll = () => {
        if (!ticking) {
          window.requestAnimationFrame(() => {
            const scrollY = window.scrollY;
            parallaxElements.forEach((el) => {
              const speed = parseFloat(el.getAttribute("data-parallax-speed") || "0.15");
              el.style.transform = `translate3d(0, ${Math.round(scrollY * speed)}px, 0)`;
            });
            ticking = false;
          });
          ticking = true;
        }
      };
      window.addEventListener("scroll", onScroll, { passive: true });
      cleanupFns.push(() => window.removeEventListener("scroll", onScroll));
    }

    // 3. Generic Interaction Listeners (Evidence-backed only)
    // Menu toggles
    const toggleButtons = document.querySelectorAll("[data-toggle-target]");
    toggleButtons.forEach((btn) => {
      const targetSelector = btn.getAttribute("data-toggle-target");
      if (!targetSelector) return;
      try {
        const targetEl = document.querySelector(targetSelector) as HTMLElement;
        if (!targetEl) return;

        const onClick = () => {
          const isExpanded = btn.getAttribute("aria-expanded") === "true";
          btn.setAttribute("aria-expanded", isExpanded ? "false" : "true");
          targetEl.classList.toggle("is-open", !isExpanded);
        };
        btn.addEventListener("click", onClick);
        cleanupFns.push(() => btn.removeEventListener("click", onClick));
      } catch {}
    });

    // Accordions
    const accordionTriggers = document.querySelectorAll("[data-accordion-trigger]");
    accordionTriggers.forEach((trigger) => {
      const content = trigger.nextElementSibling as HTMLElement;
      if (!content) return;
      const onAccordionClick = () => {
        const open = trigger.getAttribute("aria-expanded") === "true";
        trigger.setAttribute("aria-expanded", open ? "false" : "true");
        content.style.display = open ? "none" : "block";
      };
      trigger.addEventListener("click", onAccordionClick);
      cleanupFns.push(() => trigger.removeEventListener("click", onAccordionClick));
    });

    // Tab switchers
    const tabTriggers = document.querySelectorAll("[data-tab-target]");
    tabTriggers.forEach((tab) => {
      const targetId = tab.getAttribute("data-tab-target");
      if (!targetId) return;
      const onTabClick = () => {
        const parent = tab.closest("[data-tab-group]") || document.body;
        parent.querySelectorAll("[data-tab-target]").forEach((t) => t.classList.remove("active"));
        parent.querySelectorAll("[data-tab-panel]").forEach((p) => ((p as HTMLElement).style.display = "none"));
        tab.classList.add("active");
        const panel = parent.querySelector(`[data-tab-panel="${targetId}"]`) as HTMLElement;
        if (panel) panel.style.display = "block";
      };
      tab.addEventListener("click", onTabClick);
      cleanupFns.push(() => tab.removeEventListener("click", onTabClick));
    });

    return () => {
      cleanupFns.forEach((fn) => fn());
    };
  }, [animations]);

  return null;
}
""",
        )

        # 2. FramerAppearRuntime.tsx (Backwards-compatible adapter re-export)
        self._text(
            "components/FramerAppearRuntime.tsx",
            """\"use client\";

import MotionRuntime, { MotionConfig, AppearConfig } from "./MotionRuntime";

export type { MotionConfig, AppearConfig };
export default MotionRuntime;
""",
        )

        # 3. CursorFollower.tsx
        self._text(
            "components/CursorFollower.tsx",
            """\"use client\";

import CursorRuntime, { CursorFollower as CursorFollowerAlias } from "./CursorRuntime";

export { CursorFollowerAlias as CursorFollower };
export default CursorRuntime;
""",
        )

        # 4. LiveClock.tsx (Generic time emitter without hardcoded snapshot defaults)
        self._text(
            "components/LiveClock.tsx",
            """\"use client\";

import React, { useState, useEffect } from "react";

export default function LiveClock({ initialTime = "" }: { initialTime?: string }) {
  const [time, setTime] = useState(initialTime || "--:--:--");

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(now.toLocaleTimeString("en-GB", { hour12: false }));
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return <span suppressHydrationWarning>{time}</span>;
}
""",
        )

        # 5. InteractionRuntime.tsx (Universal behavioral execution engine)
        self._text(
            "components/InteractionRuntime.tsx",
            """\"use client\";

import { useEffect } from "react";

export interface TriggerSpec {
  type: string;
  selector: string;
  target_id?: string;
  event_options?: Record<string, any>;
}

export interface ActionSpec {
  type: string;
  target?: string;
  target_route?: string;
  transition?: Record<string, any>;
}

export interface InteractionConfig {
  id: string;
  category?: string;
  trigger: TriggerSpec;
  action: ActionSpec;
  states?: Record<string, Record<string, any>>;
  animation?: Record<string, any>;
  conditions?: Record<string, any>;
  evidence?: Record<string, any>;
  description?: string;
}

export interface InteractionRuntimeProps {
  interactions?: InteractionConfig[];
}

export default function InteractionRuntime({
  interactions = [],
}: InteractionRuntimeProps) {
  useEffect(() => {
    if (!interactions || interactions.length === 0) return;
    if (typeof window === "undefined") return;

    const cleanupFns: Array<() => void> = [];

    interactions.forEach((interaction) => {
      const triggerSpec = interaction.trigger;
      const actionSpec = interaction.action;
      if (!triggerSpec || !triggerSpec.selector) return;

      const findElements = (selector: string): HTMLElement[] => {
        if (!selector) return [];
        try {
          const bslash = String.fromCharCode(92);
          const cleanSel = selector.split(bslash + bslash).join(bslash).split(bslash + " ").join(" ");

          if (cleanSel.startsWith("#") && !cleanSel.includes(" ") && !cleanSel.includes(">") && !cleanSel.includes("[")) {
            const idVal = cleanSel.slice(1);
            const el = document.getElementById(idVal);
            if (el) return [el];
            const byAttr = document.querySelector(`[id="${idVal}"]`);
            if (byAttr instanceof HTMLElement) return [byAttr];
          }

          const els = Array.from(document.querySelectorAll(cleanSel)) as HTMLElement[];
          if (els.length > 0) return els;

          const stripped = selector.split(bslash).join("");
          const els2 = Array.from(document.querySelectorAll(stripped)) as HTMLElement[];
          if (els2.length > 0) return els2;

          return Array.from(document.querySelectorAll(selector)) as HTMLElement[];
        } catch (e) {
          return [];
        }
      };

      const triggers = findElements(triggerSpec.selector);
      const targets = actionSpec.target ? findElements(actionSpec.target) : [];

      let isOpen = false;

      // Handle continuous visual animation if present
      if (interaction.animation?.continuous) {
        triggers.forEach((trig) => {
          trig.setAttribute("data-continuous-motion", "true");
        });
      }

      // Dynamic target resolver (handles dynamic mounts / client-rendered DOM nodes)
      const getTargets = (): HTMLElement[] => {
        const found = actionSpec.target ? findElements(actionSpec.target) : [];
        return found.length > 0 ? found : targets;
      };

      // Support evidence-backed revealed navigation links overlay for menus
      let menuOverlay: HTMLElement | null = null;
      const revealedLinks = interaction.evidence?.revealed_links || [];
      if (interaction.category === "menu" && revealedLinks.length > 0) {
        const overlayId = `revealed-menu-overlay-${interaction.id}`;
        let existing = document.getElementById(overlayId);
        if (!existing) {
          menuOverlay = document.createElement("div");
          menuOverlay.id = overlayId;
          menuOverlay.style.position = "fixed";
          menuOverlay.style.inset = "0";
          menuOverlay.style.backgroundColor = "rgba(10, 10, 10, 0.96)";
          menuOverlay.style.backdropFilter = "blur(16px)";
          menuOverlay.style.zIndex = "9990";
          menuOverlay.style.display = "none";
          menuOverlay.style.flexDirection = "column";
          menuOverlay.style.alignItems = "center";
          menuOverlay.style.justifyContent = "center";
          menuOverlay.style.gap = "28px";
          menuOverlay.style.opacity = "0";
          menuOverlay.style.transition = "opacity 0.25s ease-in-out";

          const closeBtn = document.createElement("button");
          closeBtn.innerHTML = "&times;";
          closeBtn.style.position = "absolute";
          closeBtn.style.top = "32px";
          closeBtn.style.right = "40px";
          closeBtn.style.background = "none";
          closeBtn.style.border = "none";
          closeBtn.style.color = "#ffffff";
          closeBtn.style.fontSize = "40px";
          closeBtn.style.cursor = "pointer";
          closeBtn.onclick = () => {
            isOpen = false;
            applyState("closed");
          };
          menuOverlay.appendChild(closeBtn);

          const navEl = document.createElement("nav");
          navEl.style.display = "flex";
          navEl.style.flexDirection = "column";
          navEl.style.alignItems = "center";
          navEl.style.gap = "24px";

          revealedLinks.forEach((link: { href: string; text: string }) => {
            const a = document.createElement("a");
            a.href = link.href.startsWith("./") ? "/" + link.href.slice(2) : link.href;
            a.textContent = link.text;
            a.style.color = "#ffffff";
            a.style.fontSize = "clamp(24px, 4vw, 36px)";
            a.style.fontWeight = "700";
            a.style.letterSpacing = "0.05em";
            a.style.textDecoration = "none";
            a.style.transition = "opacity 0.2s ease, transform 0.2s ease";
            a.onmouseenter = () => {
              a.style.opacity = "0.7";
              a.style.transform = "translateX(6px)";
            };
            a.onmouseleave = () => {
              a.style.opacity = "1";
              a.style.transform = "translateX(0)";
            };
            a.onclick = () => {
              isOpen = false;
              applyState("closed");
            };
            navEl.appendChild(a);
          });

          menuOverlay.appendChild(navEl);
          document.body.appendChild(menuOverlay);
          cleanupFns.push(() => {
            if (menuOverlay && menuOverlay.parentNode) {
              menuOverlay.parentNode.removeChild(menuOverlay);
            }
          });
        } else {
          menuOverlay = existing;
        }
      }

      // State application helper
      const applyState = (stateName: "closed" | "open") => {
        const stateProps = interaction.states?.[stateName] || {};
        const currentTargets = getTargets();
        currentTargets.forEach((target) => {
          if (stateProps.display !== undefined) {
            target.style.display = stateProps.display;
          } else if (stateName === "closed") {
            target.style.display = "none";
          } else {
            target.style.display = "block";
          }

          if (stateProps.visibility !== undefined) {
            target.style.visibility = stateProps.visibility;
          } else {
            target.style.visibility = stateName === "open" ? "visible" : "hidden";
          }

          if (stateProps.opacity !== undefined) {
            target.style.opacity = String(stateProps.opacity);
          } else {
            target.style.opacity = stateName === "open" ? "1" : "0";
          }

          if (stateProps.transform !== undefined) {
            target.style.transform = stateProps.transform;
          }

          target.style.pointerEvents = stateName === "open" ? "auto" : "none";
          target.setAttribute("data-state", stateName);
          if (stateName === "open") {
            target.classList.add("active", "open");
            target.classList.remove("closed");
          } else {
            target.classList.remove("active", "open");
            target.classList.add("closed");
          }
        });

        if (menuOverlay) {
          if (stateName === "open") {
            menuOverlay.style.display = "flex";
            requestAnimationFrame(() => {
              if (menuOverlay) menuOverlay.style.opacity = "1";
            });
          } else {
            menuOverlay.style.opacity = "0";
            setTimeout(() => {
              if (menuOverlay && !isOpen) menuOverlay.style.display = "none";
            }, 250);
          }
        }

        triggers.forEach((trig) => {
          trig.setAttribute("aria-expanded", stateName === "open" ? "true" : "false");
          trig.setAttribute("data-state", stateName);
          if (stateName === "open") {
            trig.classList.add("active", "open");
            trig.classList.remove("closed");
          } else {
            trig.classList.remove("active", "open");
            trig.classList.add("closed");
          }
        });
      };

      // Apply initial state (close actions start open; toggle/open start closed)
      if (actionSpec.type === "close") {
        isOpen = true;
        applyState("open");
      } else {
        applyState("closed");
      }

      const onTriggerClick = (e: MouseEvent) => {
        if (actionSpec.type === "toggle" || interaction.category === "menu") {
          isOpen = !isOpen;
          applyState(isOpen ? "open" : "closed");
        } else if (actionSpec.type === "open") {
          isOpen = true;
          applyState("open");
        } else if (actionSpec.type === "close") {
          isOpen = false;
          applyState("closed");
        } else if (actionSpec.type === "tab_select" || interaction.category === "tabs") {
          const trig = e.currentTarget as HTMLElement | null;
          if (trig) {
            const group = trig.closest("[data-tab-group]") || trig.parentElement;
            if (group) {
              group.querySelectorAll("[data-state='open']").forEach((el) => {
                (el as HTMLElement).setAttribute("data-state", "closed");
                (el as HTMLElement).style.display = "none";
                (el as HTMLElement).classList.remove("active", "open");
              });
            }
          }
          isOpen = true;
          applyState("open");
        }
      };

      const onTriggerHover = () => {
        applyState("open");
      };

      const onTriggerLeave = () => {
        applyState("closed");
      };

      triggers.forEach((trig) => {
        if (triggerSpec.type === "click") {
          trig.addEventListener("click", onTriggerClick);
          cleanupFns.push(() => trig.removeEventListener("click", onTriggerClick));
        } else if (triggerSpec.type === "hover") {
          trig.addEventListener("mouseenter", onTriggerHover);
          trig.addEventListener("mouseleave", onTriggerLeave);
          cleanupFns.push(() => {
            trig.removeEventListener("mouseenter", onTriggerHover);
            trig.removeEventListener("mouseleave", onTriggerLeave);
          });
        }
      });
    });

    return () => {
      cleanupFns.forEach((fn) => fn());
    };
  }, [interactions]);

  return null;
}
""",
        )

        # 6. RouteTransition.tsx (Route transition visual effect)
        self._text(
            "components/RouteTransition.tsx",
            """\"use client\";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

export default function RouteTransition() {
  const pathname = usePathname();
  const [animating, setAnimating] = useState(false);

  useEffect(() => {
    setAnimating(true);
    const timer = setTimeout(() => setAnimating(false), 350);
    return () => clearTimeout(timer);
  }, [pathname]);

  if (!animating) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.2)",
        backdropFilter: "blur(4px)",
        pointerEvents: "none",
        zIndex: 9998,
        transition: "opacity 0.35s ease-out",
        opacity: animating ? 1 : 0,
      }}
    />
  );
}
""",
        )

        # 7. CursorRuntime.tsx (Evidence-driven custom cursor runtime)
        self._text(
            "components/CursorRuntime.tsx",
            """\"use client\";

import React, { useState, useEffect } from "react";

export function CursorFollower() {
  return null;
}

export default function CursorRuntime() {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [hoverText, setHoverText] = useState("");
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Suppress native cursor while custom cursor is active
    document.body.classList.add("has-custom-cursor");

    const onMove = (e: MouseEvent) => {
      setPos({ x: e.clientX, y: e.clientY });
      setVisible(true);

      const target = e.target as HTMLElement | null;
      if (target) {
        const interactive = target.closest("a, button, [role='button'], .project-card, [data-cursor]");
        if (interactive) {
          setIsHovered(true);
          const customText = interactive.getAttribute("data-cursor") || (interactive.classList.contains("project-card") ? "VIEW" : "");
          setHoverText(customText);
        } else {
          setIsHovered(false);
          setHoverText("");
        }
      }
    };

    const onLeave = () => setVisible(false);

    window.addEventListener("mousemove", onMove);
    document.body.addEventListener("mouseleave", onLeave);
    return () => {
      document.body.classList.remove("has-custom-cursor");
      window.removeEventListener("mousemove", onMove);
      document.body.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  if (!pos || !visible) return null;

  return (
    <div
      id="custom-cursor"
      style={{
        position: "fixed",
        top: pos.y,
        left: pos.x,
        transform: `translate(-50%, -50%) scale(${isHovered ? 2.2 : 1})`,
        width: isHovered && hoverText ? 36 : 14,
        height: isHovered && hoverText ? 36 : 14,
        borderRadius: "50%",
        backgroundColor: isHovered ? "rgba(255, 255, 255, 0.9)" : "var(--token-cursor, #ffffff)",
        color: "#000000",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "8px",
        fontWeight: "bold",
        pointerEvents: "none",
        zIndex: 9999,
        transition: "transform 0.15s ease-out, width 0.2s ease, height 0.2s ease, opacity 0.2s ease",
      }}
    >
      {isHovered && hoverText ? hoverText : null}
    </div>
  );
}
""",
        )

    # ---------------------------------------------------------
    # Pages
    # ---------------------------------------------------------

    def _write_pages(self):
        self._write_home_page()

        routes = self.ir.get(
            "routes",
            [],
        )

        has_work_routes = False
        has_contact_route = False

        for route in routes:
            if not route or route in ("", "/"):
                continue

            clean_route = route if route.startswith("/") else f"/{route}"

            if clean_route == "/contact":
                has_contact_route = True
                self._write_contact_page()
            elif clean_route.startswith("/work/"):
                has_work_routes = True
                self._write_work_page(clean_route)
            else:
                self._write_custom_page(clean_route)

        # Generate work pages from data if data['projects'] exists or work routes were found
        projects = self.ir.get("data", {}).get("projects", [])
        if projects or has_work_routes or any(r == "/work" or r.startswith("/work/") for r in routes):
            for p in projects:
                slug = p.get("slug")
                if slug:
                    self._write_work_page(f"/work/{slug}")
            self._write_work_dynamic_page()
            self._write_work_index_page()

        if has_contact_route or "/contact" in routes:
            self._write_contact_page()

    def _write_home_page(self):
        pages = self.ir.get("pages", [])
        page_components = []
        if pages:
            page_components = pages[0].get("components", [])

        # No hardcoded fallback — only emit what was actually found in DOM

        imports = []
        rendered = []

        for item in page_components:
            name = item.get("name") if isinstance(item, dict) else str(item)
            if name:
                imports.append(f'import {name} from "../components/{name}";')
                rendered.append(f"      <{name} />")

        content_root, _ = self.emitter.decompose_content_sections(self.emitter.tree) if self.emitter else (None, [])
        wrapper_open = ""
        wrapper_close = ""
        if content_root and content_root.get("tag"):
            c_tag = content_root.get("tag", "div")
            c_classes = " ".join(content_root.get("classes", [])).strip()
            c_cls_attr = f' className="{c_classes}"' if c_classes else ""
            c_style = content_root.get("attributes", {}).get("style", "")
            c_style_jsx = self.emitter._parse_style_attribute(c_style) if c_style else ""
            c_id = content_root.get("id")
            c_id_attr = f' id="{c_id}"' if c_id else ""

            if c_tag == "main":
                main_open = f"<main{c_cls_attr}{c_id_attr}{c_style_jsx}>"
                main_close = "</main>"
            else:
                main_open = "<main>"
                main_close = "</main>"
                wrapper_open = f"      <{c_tag}{c_cls_attr}{c_id_attr}{c_style_jsx}>\n"
                wrapper_close = f"      </{c_tag}>\n"
        else:
            main_open = "<main>"
            main_close = "</main>"

        body_rendered = "\n".join(f"  {r}" if wrapper_open else r for r in rendered)
        content = (
            "\n".join(imports)
            + "\n\n"
            + f"""export default function Home() {{
  return (
    {main_open}
{wrapper_open}{body_rendered}
{wrapper_close}    {main_close}
  );
}}
"""
        )

        self._text("app/page.tsx", content)

    def _rel_components_path(self, segment: str) -> str:
        depth = len(segment.strip("/").split("/")) + 1
        return "../" * depth + "components"

    def _write_contact_page(self):
        pages = self.ir.get("pages", [])
        matched = next((p for p in pages if p.get("route") in ("/contact", "contact")), None)
        if matched and matched.get("dom"):
            jsx_body = self.emitter.emit_jsx(matched["dom"], depth=3, is_root=False)
            self._text(
                "app/contact/page.tsx",
                f"""import React from "react";

export default function ContactPage() {{
  return (
    <main>
{jsx_body}    </main>
  );
}}
""",
            )
            return

        # Fallback: route was not captured — emit notice, not fabricated content
        title = self._title_from_slug("contact")
        self._text(
            "app/contact/page.tsx",
            f"""import React from "react";

export default function ContactPage() {{
  return (
    <main>
      <section style={{{{ maxWidth: "1200px", margin: "0 auto", padding: "120px 24px 80px", minHeight: "60vh" }}}}>
        <h1 style={{{{ fontFamily: "var(--font-display)", fontSize: "clamp(36px, 6vw, 64px)", fontWeight: 700 }}}}>
          {title}
        </h1>
        <p style={{{{ opacity: 0.6, marginTop: "16px" }}}}>
          This page was not captured during site extraction.
        </p>
      </section>
    </main>
  );
}}
""",
        )

    def _find_nav_and_footer(self) -> tuple[Optional[str], Optional[str]]:
        pages = self.ir.get("pages", [])
        page_components = pages[0].get("components", []) if pages else []

        comp_items: list[tuple[str, str]] = []
        for item in page_components:
            if isinstance(item, dict):
                comp_items.append((item.get("name", ""), item.get("role", "")))
            elif isinstance(item, str):
                comp_items.append((item, ""))

        nav_name: Optional[str] = None
        footer_name: Optional[str] = None

        for name, role in comp_items:
            if not name:
                continue
            nl = name.lower()
            if role in ("navigation", "header") or nl in ("nav", "navbar", "headernavigation", "header", "navigation"):
                nav_name = name
                break
        if not nav_name:
            for name, _ in comp_items:
                nl = name.lower()
                if "nav" in nl or "header" in nl:
                    nav_name = name
                    break

        for name, role in comp_items:
            if not name:
                continue
            nl = name.lower()
            if role == "footer" or nl in ("footer", "sitefooter", "pagefooter"):
                footer_name = name
                break
        if not footer_name:
            for name, _ in comp_items:
                nl = name.lower()
                if "footer" in nl:
                    footer_name = name
                    break

        return nav_name, footer_name

    def _write_work_index_page(self):
        pages = self.ir.get("pages", [])
        matched = next((p for p in pages if p.get("route") in ("/work", "work")), None)
        if matched and matched.get("dom"):
            jsx_body = self.emitter.emit_jsx(matched["dom"], depth=3, is_root=False)
            self._text(
                "app/work/page.tsx",
                f"""import React from "react";

export default function WorkIndexPage() {{
  return (
    <main>
{jsx_body}
    </main>
  );
}}
""",
            )
            return

        nav_name, footer_name = self._find_nav_and_footer()
        nav_import = f'import {nav_name} from "../../components/{nav_name}";\n' if nav_name else ""
        nav_tag = f"      <{nav_name} />\n" if nav_name else ""
        footer_import = f'import {footer_name} from "../../components/{footer_name}";\n' if footer_name else ""
        footer_tag = f"      <{footer_name} />\n" if footer_name else ""

        projects = self.ir.get("data", {}).get("projects", [])
        project_cards = []
        for p in projects:
            slug = p.get("slug") or self._slugify(p.get("title", ""))
            title = p.get("title", "Project")
            cat = p.get("category") or "Featured"
            img = p.get("image")
            img_el = f'<img src="{img}" alt="{title}" style={{{{ width: "100%", height: "240px", objectFit: "cover", borderRadius: "12px", marginBottom: "16px" }}}} />' if img else ""
            project_cards.append(f"""          <a
            key="{slug}"
            href="/work/{slug}"
            style={{{{ display: "flex", flexDirection: "column", padding: "24px", borderRadius: "16px", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", textDecoration: "none", color: "inherit" }}}}
          >
            {img_el}
            <span style={{{{ fontSize: "12px", fontFamily: "var(--font-mono, monospace)", textTransform: "uppercase", opacity: 0.6, marginBottom: "8px" }}}}>{cat}</span>
            <h2 style={{{{ fontSize: "24px", fontWeight: 700, margin: "0 0 8px 0", fontFamily: "var(--font-display)" }}}}>{title}</h2>
            <p style={{{{ fontSize: "14px", opacity: 0.8, lineHeight: 1.5, margin: 0 }}}}>{p.get("description", "")}</p>
          </a>""")

        cards_markup = "\n".join(project_cards) if project_cards else "          <p style={{ opacity: 0.6 }}>No projects listed.</p>"

        self._text(
            "app/work/page.tsx",
            f"""import React from "react";
{nav_import}{footer_import}
export default function WorkIndexPage() {{
  return (
    <main>
{nav_tag}      <section style={{{{ maxWidth: "1200px", margin: "0 auto", padding: "120px 24px 80px", minHeight: "70vh" }}}}>
        <p style={{{{ fontFamily: "var(--font-mono, monospace)", fontSize: "14px", letterSpacing: "0.1em", opacity: 0.7, marginBottom: "16px" }}}}>// PORTFOLIO</p>
        <h1 style={{{{ fontFamily: "var(--font-display)", fontSize: "clamp(40px, 6vw, 72px)", fontWeight: 700, margin: "0 0 32px 0" }}}}>
          Selected Work
        </h1>
        <div style={{{{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "24px", marginTop: "32px" }}}}>
{cards_markup}
        </div>
      </section>
{footer_tag}    </main>
  );
}}
""",
        )

    def _write_work_dynamic_page(self):
        nav_name, footer_name = self._find_nav_and_footer()
        nav_import = f'import {nav_name} from "../../../components/{nav_name}";\n' if nav_name else ""
        nav_tag = f"      <{nav_name} />\n" if nav_name else ""
        footer_import = f'import {footer_name} from "../../../components/{footer_name}";\n' if footer_name else ""
        footer_tag = f"      <{footer_name} />\n" if footer_name else ""

        self._text(
            "app/work/[slug]/page.tsx",
            f"""import React from "react";
{nav_import}{footer_import}import {{ projects }} from "../../../data/projects";

type WorkPageProps = {{
  params: Promise<{{ slug: string }}>;
}};

export default async function DynamicWorkPage({{ params }}: WorkPageProps) {{
  const {{ slug }} = await params;
  const proj = projects.find(
    (p: any) => p.slug === slug || p.title.toLowerCase().replace(/\\s+/g, "-") === slug
  );
  const title = proj?.title || slug.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  const desc = proj?.description || `Case study for ${{title}}.`;
  const image = proj?.image;

  return (
    <main>
{nav_tag}      <article style={{{{ maxWidth: "1200px", margin: "0 auto", padding: "120px 24px 80px", minHeight: "70vh" }}}}>
        <div style={{{{ marginBottom: "24px" }}}}>
          <a href="/" style={{{{ opacity: 0.6, textDecoration: "none", fontSize: "14px", fontFamily: "var(--font-mono, monospace)" }}}}>
            ← Back to Overview
          </a>
        </div>
        <h1 style={{{{ fontFamily: "var(--font-display)", fontSize: "clamp(40px, 6vw, 72px)", fontWeight: 700, margin: "0 0 24px 0" }}}}>
          {{title}}
        </h1>
        <p style={{{{ fontFamily: "var(--font-body)", fontSize: "20px", opacity: 0.8, lineHeight: 1.6, maxWidth: "720px" }}}}>
          {{desc}}
        </p>
        {{image && (
          <img src={{image}} alt={{title}} style={{{{ width: "100%", maxHeight: "640px", objectFit: "cover", borderRadius: "16px", margin: "40px 0" }}}} />
        )}}
      </article>
{footer_tag}    </main>
  );
}}
""",
        )

    def _write_work_page(self, route: str):
        slug = route.rstrip("/").split("/")[-1]
        title = self._title_from_slug(slug)
        pages = self.ir.get("pages", [])
        matched = next((p for p in pages if p.get("route") == route or p.get("route") == f"/work/{slug}"), None)

        if matched and matched.get("dom"):
            jsx_body = self.emitter.emit_jsx(matched["dom"], depth=3, is_root=False)
            self._text(
                f"app/work/{slug}/page.tsx",
                f"""import React from "react";

export default function WorkPage() {{
  return (
    <main>
{jsx_body}
    </main>
  );
}}
""",
            )
            return

        nav_name, footer_name = self._find_nav_and_footer()
        nav_import = f'import {nav_name} from "../../../components/{nav_name}";\n' if nav_name else ""
        nav_tag = f"      <{nav_name} />\n" if nav_name else ""
        footer_import = f'import {footer_name} from "../../../components/{footer_name}";\n' if footer_name else ""
        footer_tag = f"      <{footer_name} />\n" if footer_name else ""

        projects = self.ir.get("data", {}).get("projects", [])
        proj = next((p for p in projects if p.get("slug") == slug or self._slugify(p.get("title", "")) == slug), None)

        proj_title = proj.get("title") if proj else title
        proj_cat = proj.get("category") if proj else "Featured"
        proj_img = proj.get("image") if proj else None
        proj_desc = proj.get("description") if proj else f"Detailed overview for {proj_title}."
        proj_tags = (proj.get("tags") if proj else None) or ([proj_cat] if proj_cat else ["Featured"])

        img_markup = f'<img src="{proj_img}" alt="{proj_title}" style={{{{ width: "100%", maxHeight: "640px", objectFit: "cover", borderRadius: "16px", margin: "40px 0" }}}} />' if proj_img else ""
        tags_markup = "\n".join([f'          <span key="{i}" style={{{{ padding: "6px 14px", borderRadius: "9999px", background: "rgba(255,255,255,0.08)", fontSize: "14px", fontFamily: "var(--font-mono, monospace)" }}}}>{t}</span>' for i, t in enumerate(proj_tags)])

        self._text(
            f"app/work/{slug}/page.tsx",
            f"""import React from "react";
{nav_import}{footer_import}
export default function WorkPage() {{
  return (
    <main>
{nav_tag}      <article style={{{{ maxWidth: "1200px", margin: "0 auto", padding: "120px 24px 80px", minHeight: "70vh" }}}}>
        <div style={{{{ marginBottom: "24px" }}}}>
          <a href="/" style={{{{ opacity: 0.6, textDecoration: "none", fontSize: "14px", fontFamily: "var(--font-mono, monospace)" }}}}>
            ← Back to Overview
          </a>
        </div>
        <p style={{{{ fontFamily: "var(--font-mono, monospace)", fontSize: "14px", letterSpacing: "0.1em", opacity: 0.7, marginBottom: "8px", textTransform: "uppercase" }}}}>
          {proj_cat}
        </p>
        <h1 style={{{{ fontFamily: "var(--font-display)", fontSize: "clamp(40px, 6vw, 72px)", fontWeight: 700, margin: "0 0 24px 0" }}}}>
          {proj_title}
        </h1>
        <p style={{{{ fontFamily: "var(--font-body)", fontSize: "20px", opacity: 0.8, lineHeight: 1.6, maxWidth: "720px" }}}}>
          {proj_desc}
        </p>
        <div style={{{{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "24px" }}}}>
{tags_markup}
        </div>
        {img_markup}
      </article>
{footer_tag}    </main>
  );
}}
""",
        )

    def _write_custom_page(self, route: str):
        segment = route.strip("/")
        title = self._title_from_slug(segment.split("/")[-1])
        pages = self.ir.get("pages", [])
        matched = next((p for p in pages if p.get("route") == route or p.get("route") == f"/{segment}"), None)
        comp_name = "".join(w.capitalize() for w in re.split(r"[^a-zA-Z0-9]", segment)) + "Page"

        if matched and matched.get("dom"):
            jsx_body = self.emitter.emit_jsx(matched["dom"], depth=3, is_root=False)
            self._text(
                f"app/{segment}/page.tsx",
                f"""import React from "react";

export default function {comp_name}() {{
  return (
    <main>
{jsx_body}    </main>
  );
}}
""",
            )
            return

        # Fallback: route was not captured — emit notice, not fabricated content
        self._text(
            f"app/{segment}/page.tsx",
            f"""import React from "react";

export default function {comp_name}() {{
  return (
    <main>
      <section style={{{{ maxWidth: "1200px", margin: "0 auto", padding: "120px 24px 80px", minHeight: "60vh" }}}}>
        <h1 style={{{{ fontFamily: "var(--font-display)", fontSize: "clamp(36px, 6vw, 64px)", fontWeight: 700 }}}}>
          {title}
        </h1>
        <p style={{{{ opacity: 0.6, marginTop: "16px" }}}}>
          This page was not captured during site extraction.
        </p>
      </section>
    </main>
  );
}}
""",
        )

    def _write_not_found_page(self):
        """Next.js requires a dedicated app/not-found.tsx to render a custom 404
        instead of the framework default. Use captured /404 content if the crawl
        found a real 404 route; otherwise emit a branded fallback using the
        site's own nav/footer components."""
        pages = self.ir.get("pages", [])
        matched = next(
            (p for p in pages if p.get("route") in ("/404", "404", "/not-found")),
            None,
        )

        if matched and matched.get("dom"):
            jsx_body = self.emitter.emit_jsx(matched["dom"], depth=3, is_root=False)
            self._text(
                "app/not-found.tsx",
                f"""import React from "react";

export default function NotFound() {{
  return (
    <main>
{jsx_body}    </main>
  );
}}
""",
            )
            return

        nav_name, footer_name = self._find_nav_and_footer()
        nav_import = f'import {nav_name} from "../components/{nav_name}";\n' if nav_name else ""
        nav_tag = f"      <{nav_name} />\n" if nav_name else ""
        footer_import = f'import {footer_name} from "../components/{footer_name}";\n' if footer_name else ""
        footer_tag = f"      <{footer_name} />\n" if footer_name else ""

        self._text(
            "app/not-found.tsx",
            f"""import React from "react";
{nav_import}{footer_import}
export default function NotFound() {{
  return (
    <main>
{nav_tag}      <section style={{{{ maxWidth: "1200px", margin: "0 auto", padding: "160px 24px 120px", minHeight: "60vh", textAlign: "center" }}}}>
        <h1 style={{{{ fontFamily: "var(--font-display)", fontSize: "clamp(48px, 8vw, 96px)", fontWeight: 700 }}}}>
          404
        </h1>
        <p style={{{{ opacity: 0.6, marginTop: "16px" }}}}>
          This page could not be found.
        </p>
        <a href="/" style={{{{ display: "inline-block", marginTop: "32px", textDecoration: "underline" }}}}>
          ← Back home
        </a>
      </section>
{footer_tag}    </main>
  );
}}
""",
        )

    # ---------------------------------------------------------
    # Data
    # ---------------------------------------------------------

    def _write_data(self):
        data_ir = self.ir.get("data", {})

        # Projects
        projects = data_ir.get("projects", [])
        if not projects or (len(projects) == 1 and "INTRO" in projects[0].get("title", "")):
            extracted = self.emitter.extract_projects()
            if extracted:
                projects = extracted

        self._text(
            "data/projects.ts",
            """export type Project = {
  title: string;
  slug?: string;
  description?: string;
  category?: string;
  image?: string | null;
  tags?: string[];
};

export const projects: Project[] = """
            + json.dumps(projects, indent=2)
            + ";\n",
        )

        # Capabilities
        capabilities = data_ir.get("capabilities", [])
        self._text(
            "data/capabilities.ts",
            """export type Capability = {
  title: string;
  description: string;
};

export const capabilities: Capability[] = """
            + json.dumps(capabilities, indent=2)
            + ";\n",
        )

        # Journey
        journey = data_ir.get("journey", [])
        self._text(
            "data/journey.ts",
            """export type JourneyTimeline = {
  period: string;
  role: string;
  description: string;
};

export const journey: JourneyTimeline[] = """
            + json.dumps(journey, indent=2)
            + ";\n",
        )

        # Toolkit
        toolkit = data_ir.get("toolkit", [])
        self._text(
            "data/toolkit.ts",
            """export type ToolkitSkill = {
  name: string;
  category?: string;
};

export const toolkit: ToolkitSkill[] = """
            + json.dumps(toolkit, indent=2)
            + ";\n",
        )


    # ---------------------------------------------------------
    # Analysis copy
    # ---------------------------------------------------------

    def _write_analysis(self):
        self._json(
            "analysis/source-ir.json",
            self.ir,
        )
        self._json(
            "analysis/site_ir.json",
            self.ir,
        )
        self._json(
            "analysis/asset_bindings.json",
            self.ir.get("asset_bindings", []),
        )
        if self.ir.get("typography"):
            self._json(
                "analysis/typography.json",
                self.ir["typography"],
            )
        if self.ir.get("layout"):
            self._json(
                "analysis/layout.json",
                self.ir["layout"],
            )


    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _component_name(
        self,
        component: dict[str, Any],
    ) -> str:
        name = (
            component.get("name")
            or component.get("component")
            or component.get("tag")
            or "Component"
        )

        name = re.sub(
            r"[^a-zA-Z0-9 ]+",
            " ",
            str(name),
        )

        words = name.split()

        result = "".join(
            word[:1].upper() + word[1:]
            for word in words
        )


        if not result:
            result = "Component"

        if result[0].isdigit():
            result = "Component" + result

        return result

    @staticmethod
    def _class_name(
        name: str,
    ) -> str:
        result = re.sub(
            r"(?<!^)(?=[A-Z])",
            "-",
            name,
        )

        return result.lower()

    @staticmethod
    def _css_name(
        name: str,
    ) -> str:
        return re.sub(
            r"[^a-zA-Z0-9_-]+",
            "-",
            str(name),
        ).strip("-").lower()

    @staticmethod
    def _to_kebab(name: str) -> str:
        return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()

    @staticmethod
    def _escape_jsx(
        text: str,
    ) -> str:
        if not text:
            return ""

        return (
            str(text)
            .replace("{", "&#123;")
            .replace("}", "&#125;")
        )

    @staticmethod
    def _title_from_slug(
        slug: str,
    ) -> str:
        return slug.replace(
            "-",
            " ",
        ).title()

    @staticmethod
    def _slugify(text: str) -> str:
        return re.sub(r"[^a-zA-Z0-9]+", "-", str(text).lower()).strip("-")

    @staticmethod
    def _project_name() -> str:
        return "reconstructed-site"

    def _resolve_component_imports(self, relative: str, content: str) -> str:
        if not relative.endswith((".tsx", ".jsx", ".ts", ".js")):
            return content

        parts = Path(relative).parts[:-1]

        def get_rel_import(target_comp: str) -> str:
            if not parts or parts == (".",):
                return f"./components/{target_comp}"
            if parts[0] == "components":
                depth = len(parts) - 1
                return ("../" * depth if depth > 0 else "./") + target_comp
            depth = len(parts)
            return ("../" * depth) + f"components/{target_comp}"

        runtime_components = ["LiveClock", "CursorRuntime", "InteractionRuntime", "MotionRuntime", "RouteTransition"]

        for comp in runtime_components:
            if relative == f"components/{comp}.tsx":
                continue
            if re.search(rf"<\s*{comp}\b", content) and not re.search(rf"\bimport\b.*\b{comp}\b", content):
                import_path = get_rel_import(comp)
                import_stmt = f'import {comp} from "{import_path}";\n'
                if content.startswith('"use client"') or content.startswith("'use client'"):
                    lines = content.split("\n", 1)
                    content = lines[0] + "\n" + import_stmt + (lines[1] if len(lines) > 1 else "")
                else:
                    content = import_stmt + content

        return content

    def _text(
        self,
        relative: str,
        content: str,
    ):
        content = self._resolve_component_imports(relative, content)
        path = self.output / relative
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            content,
            encoding="utf-8",
        )

    def _json(
        self,
        relative: str,
        value: Any,
    ):
        self._text(
            relative,
            json.dumps(
                value,
                indent=2,
            ),
        )

