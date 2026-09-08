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
        self.emitter = DomToJsxEmitter(
            component_tree=self.ir.get("components"),
            asset_bindings=self.ir.get("asset_bindings", []),
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
        has_cursor = animations.get("has_cursor", False)

        layout_imports = [
            'import "../styles/tokens.css";',
            'import "./globals.css";',
            'import FramerAppearRuntime from "../components/FramerAppearRuntime";',
        ]
        layout_elements = [
            "        {children}",
            f"        <FramerAppearRuntime animations={{{json.dumps(appear_animations)}}} />",
        ]

        if has_cursor:
            layout_imports.append('import CursorFollower from "../components/CursorFollower";')
            layout_elements.append("        <CursorFollower />")

        imports_str = "\n".join(layout_imports)
        elements_str = "\n".join(layout_elements)

        self._text(
            "app/layout.tsx",
            f"""\
{imports_str}

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

        # Source-extracted rules (font-faces, relevant classes, media rules)
        source_rules = self.ir.get("component_styles", {}).get("source_rules", {})
        font_faces = source_rules.get("font_faces", [])
        class_rules = source_rules.get("class_rules", [])
        source_media_rules = source_rules.get("media_rules", [])

        font_face_block = ("\n\n".join(font_faces) + "\n\n") if font_faces else ""
        source_class_block = ("\n\n/* Source Extracted Element Styles */\n" + "\n\n".join(class_rules)) if class_rules else ""
        source_media_block = ("\n\n/* Source Extracted Responsive Rules */\n" + "\n\n".join(source_media_rules)) if source_media_rules else ""

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

/* Component Classes */
""" + "\n\n".join(style_rules) + source_class_block + media_block + source_media_block

        self._text(
            "app/globals.css",
            css_content + "\n",
        )

    # ---------------------------------------------------------
    # Components
    # ---------------------------------------------------------

    def _write_components(self):
        # 1. Page-level components
        pages = self.ir.get("pages", [])
        page_components = []
        if pages:
            page_components = pages[0].get("components", [])

        # Fallback to standard component list if not in pages
        if not page_components:
            page_components = [
                "HeaderNavigation",
                "Hero",
                "Intro",
                "Projects",
                "About",
                "Capabilities",
                "VoiceOfMS",
                "Journey",
                "Toolkit",
                "CTA",
                "Footer",
            ]

        page_comp_names = set()
        for item in page_components:
            name = item.get("name") if isinstance(item, dict) else str(item)
            if name:
                page_comp_names.add(name)
                self._write_page_component(name)

        # 2. Reusable Item Components
        reusable = self.ir.get("reusable_components", [])
        if isinstance(reusable, dict):
            reusable = list(reusable.values())

        standard_reusable = [
            "ProjectCard",
            "CapabilityItem",
            "JourneyItem",
            "ToolkitItem",
            "NavItem",
        ]

        reusable_names = set()
        for item in reusable:
            name = item.get("name") if isinstance(item, dict) else str(item)
            if name:
                cleaned = self._component_name({"name": name})
                reusable_names.add(cleaned)

        for name in standard_reusable:
            reusable_names.add(name)

        for name in reusable_names:
            if name not in page_comp_names:
                self._write_reusable_component(name)

        # 3. Interactive Runtime Components
        self._write_runtime_components()

    def _write_page_component(self, name: str):
        class_name = self._class_name(name)
        node = self.emitter.find_node_for_component(name)
        asset_bindings = self.ir.get("asset_bindings", [])
        title = self.ir.get("metadata", {}).get("title") or "Website"

        if node:
            emitted_jsx = self.emitter.emit_jsx(
                node,
                depth=2,
                root_classes=f"{class_name} ${{className}}".strip(),
                root_id=name.lower() if name in ("Hero", "Projects", "About", "Capabilities", "Journey", "Toolkit", "CTA") else None,
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
        elif name == "HeaderNavigation":
            logo_binding = next(
                (b for b in asset_bindings if b.get("component") == "HeaderNavigation" and b.get("role") == "logo" and b.get("local_path")),
                None
            )
            brand_element = (
                f'<img src="{logo_binding["local_path"]}" alt="Brand Logo" style={{{{ height: "32px", width: "auto" }}}} />'
                if logo_binding
                else f'<strong>{self._escape_jsx(title)}</strong>'
            )
            code = f"""import React from "react";

type HeaderNavigationProps = {{
  className?: string;
}};

export default function HeaderNavigation({{
  className = "",
}}: HeaderNavigationProps) {{
  return (
    <header className={{"{class_name} " + className}}>
      <div className="brand-logo">
        <a href="/">{brand_element}</a>
      </div>
      <nav className="nav-links" style={{{{ fontFamily: "var(--font-body)", fontSize: "var(--type-navigation-size, 14px)", fontWeight: "var(--type-navigation-weight, 500)" }}}}>
        <a href="#work" className="nav-link">Work</a>
        <a href="#about" className="nav-link">About</a>
      </nav>
    </header>
  );
}}
"""
        elif name == "Hero":
            video_b = next(
                (b for b in asset_bindings if b.get("component") == "Hero" and b.get("role") == "video" and b.get("local_path")),
                None
            )
            poster_b = next(
                (b for b in asset_bindings if b.get("component") == "Hero" and b.get("role") == "poster" and b.get("local_path")),
                None
            )
            bg_b = next(
                (b for b in asset_bindings if b.get("component") == "Hero" and b.get("role") in ("background", "image") and b.get("local_path")),
                None
            )

            media_element = ""
            if video_b:
                poster_attr = f' poster="{poster_b["local_path"]}"' if poster_b else ""
                media_element = f"""      <video
        src="{video_b['local_path']}"{poster_attr}
        autoPlay
        muted
        loop
        playsInline
        style={{{{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", zIndex: 0, opacity: 0.25 }}}}
      />\n"""
            elif bg_b:
                media_element = f"""      <img
        src="{bg_b['local_path']}"
        alt="Hero Media"
        style={{{{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", zIndex: 0, opacity: 0.2 }}}}
      />\n"""

            code = f"""import React from "react";

type HeroProps = {{
  className?: string;
}};

export default function Hero({{
  className = "",
}}: HeroProps) {{
  return (
    <section className={{"{class_name} " + className}} id="hero" style={{{{ position: "relative", overflow: "hidden" }}}}>
{media_element}      <div style={{{{ position: "relative", zIndex: 1 }}}}>
        <h1 style={{{{ fontFamily: "var(--font-display)", fontSize: "var(--type-hero-size, clamp(48px, 8vw, 110px))", fontWeight: "var(--type-hero-weight, 800)", lineHeight: "var(--type-hero-line-height, 1.05)", margin: "24px 0" }}}}>
          {self._escape_jsx(title)}
        </h1>
        <p style={{{{ fontFamily: "var(--font-body)", fontSize: "var(--type-body-size, clamp(18px, 2.5vw, 28px))", lineHeight: "var(--type-body-line-height, 1.6)", maxWidth: "800px", opacity: 0.8 }}}}>
        </p>
      </div>
    </section>
  );
}}
"""
        elif name == "Projects":
            code = f"""import React from "react";
import ProjectCard from "./ProjectCard";
import {{ projects }} from "../data/projects";

type ProjectsProps = {{
  className?: string;
}};

export default function Projects({{
  className = "",
}}: ProjectsProps) {{
  return (
    <section className={{"{class_name} " + className}} id="work">
      <div className="section-header">
        <h2 style={{{{ fontFamily: "var(--font-display)", fontSize: "var(--type-heading-size, clamp(32px, 5vw, 64px))", fontWeight: "var(--type-heading-weight, 700)", lineHeight: "var(--type-heading-line-height, 1.15)" }}}}>Projects</h2>
      </div>
      <div className="projects-grid" style={{{{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "32px" }}}}>
        {{projects.map((project, index) => (
          <ProjectCard key={{index}} project={{project}} />
        ))}}
      </div>
    </section>
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
    <section className={{`{class_name} ${{className}}`.trim()}}>
      {{children}}
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
        # 1. FramerAppearRuntime.tsx
        self._text(
            "components/FramerAppearRuntime.tsx",
            """\"use client\";

import { useEffect } from "react";

export interface AppearConfig {
  initial?: Record<string, any>;
  animate?: Record<string, any>;
  transition?: Record<string, any>;
  [key: string]: any;
}

export default function FramerAppearRuntime({
  animations = {},
}: {
  animations?: Record<string, AppearConfig>;
}) {
  useEffect(() => {
    if (!animations || Object.keys(animations).length === 0) return;
    if (typeof window === "undefined") return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    Object.entries(animations).forEach(([appearId, config]) => {
      const el = document.querySelector(`[data-framer-appear-id="${appearId}"]`) as HTMLElement;
      if (!el) return;

      const initial = config.initial || {};
      const animate = config.animate || {};
      const transition = config.transition || {};

      const delayMs = (transition.delay || 0) * 1000;
      let durationMs = (transition.duration || 0.8) * 1000;

      if (transition.type === "spring") {
        const stiffness = transition.stiffness || 200;
        const damping = transition.damping || 40;
        durationMs = Math.max(600, Math.min(1800, (damping / (2 * Math.sqrt(stiffness))) * 1200 + 400));
      }

      const initX = initial.x !== undefined ? `${initial.x}px` : "0px";
      const initY = initial.y !== undefined ? `${initial.y}px` : "0px";
      const initScale = initial.scale !== undefined ? initial.scale : 1;
      const initRotate = initial.rotate !== undefined ? `${initial.rotate}deg` : "0deg";

      const targetX = animate.x !== undefined ? `${animate.x}px` : "0px";
      const targetY = animate.y !== undefined ? `${animate.y}px` : "0px";
      const targetScale = animate.scale !== undefined ? animate.scale : 1;
      const targetRotate = animate.rotate !== undefined ? `${animate.rotate}deg` : "0deg";

      const initTransform = `translate(${initX}, ${initY}) scale(${initScale}) rotate(${initRotate})`;
      const targetTransform = `translate(${targetX}, ${targetY}) scale(${targetScale}) rotate(${targetRotate})`;

      const initOpacity = initial.opacity !== undefined ? initial.opacity : 1;
      const targetOpacity = animate.opacity !== undefined ? animate.opacity : 1;

      try {
        el.animate(
          [
            { opacity: initOpacity, transform: initTransform },
            { opacity: targetOpacity, transform: targetTransform },
          ],
          {
            duration: durationMs,
            delay: delayMs,
            easing: "cubic-bezier(0.16, 1, 0.3, 1)",
            fill: "both",
          }
        );
      } catch (err) {
        el.style.transform = targetTransform;
        el.style.opacity = `${targetOpacity}`;
      }
    });
  }, [animations]);

  return null;
}
""",
        )

        # 2. CursorFollower.tsx
        self._text(
            "components/CursorFollower.tsx",
            """\"use client\";

import { useEffect, useState } from "react";

export default function CursorFollower() {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      setPos({ x: e.clientX, y: e.clientY });
      setVisible(true);
    };
    const onLeave = () => setVisible(false);

    window.addEventListener("mousemove", onMove);
    document.body.addEventListener("mouseleave", onLeave);
    return () => {
      window.removeEventListener("mousemove", onMove);
      document.body.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  if (!pos || !visible) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: pos.y,
        left: pos.x,
        transform: "translate(-50%, -50%)",
        width: 12,
        height: 12,
        borderRadius: "50%",
        backgroundColor: "var(--token-c46abb9d-0d10-414f-ba99-89efb980d54d, #ffffff)",
        pointerEvents: "none",
        zIndex: 9999,
        transition: "transform 0.05s ease-out, opacity 0.2s ease",
      }}
    />
  );
}
""",
        )

        # 3. LiveClock.tsx
        self._text(
            "components/LiveClock.tsx",
            """\"use client\";

import React, { useState, useEffect } from "react";

export default function LiveClock({ initialTime = "14:09:02" }: { initialTime?: string }) {
  const [time, setTime] = useState(initialTime);

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

    # ---------------------------------------------------------
    # Pages
    # ---------------------------------------------------------

    def _write_pages(self):
        self._write_home_page()

        routes = self.ir.get(
            "routes",
            [],
        )

        for route in routes:
            if not route or route in ("", "/"):
                continue

            clean_route = route if route.startswith("/") else f"/{route}"

            if clean_route == "/contact":
                self._write_contact_page()
            elif clean_route.startswith("/work/"):
                self._write_work_page(clean_route)
            else:
                self._write_custom_page(clean_route)

        # Ensure contact and dynamic work route exist
        self._write_contact_page()
        self._write_work_dynamic_page()

    def _write_home_page(self):
        pages = self.ir.get("pages", [])
        page_components = []
        if pages:
            page_components = pages[0].get("components", [])

        if not page_components:
            page_components = [
                "HeaderNavigation",
                "Hero",
                "Intro",
                "Projects",
                "About",
                "Capabilities",
                "VoiceOfMS",
                "Journey",
                "Toolkit",
                "CTA",
                "Footer",
            ]

        imports = []
        rendered = []

        for item in page_components:
            name = item.get("name") if isinstance(item, dict) else str(item)
            if name:
                imports.append(f'import {name} from "../components/{name}";')
                rendered.append(f"      <{name} />")

        content = (
            "\n".join(imports)
            + "\n\n"
            + """export default function Home() {
  return (
    <main>
"""
            + "\n".join(rendered)
            + """
    </main>
  );
}
"""
        )

        self._text("app/page.tsx", content)

    def _write_contact_page(self):
        self._text(
            "app/contact/page.tsx",
            """import React from "react";
import HeaderNavigation from "../../components/HeaderNavigation";
import Footer from "../../components/Footer";

export default function ContactPage() {
  return (
    <main>
      <HeaderNavigation />
      <section style={{ maxWidth: "1200px", margin: "0 auto", padding: "120px 24px 80px", minHeight: "60vh" }}>
        <p style={{ fontFamily: "var(--font-mono, monospace)", fontSize: "14px", letterSpacing: "0.1em", opacity: 0.7, marginBottom: "16px" }}>// CONTACT</p>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: "clamp(48px, 8vw, 96px)", fontWeight: 700, lineHeight: 1, margin: "0 0 32px 0" }}>
          LET'S BUILD TOGETHER
        </h1>
        <p style={{ fontFamily: "var(--font-body)", fontSize: "20px", maxWidth: "600px", opacity: 0.8, lineHeight: 1.6, marginBottom: "48px" }}>
          Available for innovative projects worldwide. Combining design engineering, machine learning, and high-performance interfaces.
        </p>
        <div style={{ display: "flex", gap: "24px", flexWrap: "wrap", marginBottom: "64px" }}>
          <a
            href="mailto:contact@example.com"
            style={{ display: "inline-flex", alignItems: "center", padding: "16px 32px", borderRadius: "9999px", background: "var(--color-foreground, #ffffff)", color: "var(--color-background, #0a0a0a)", fontWeight: 600, textDecoration: "none" }}
          >
            GET IN TOUCH
          </a>
          <a
            href="/"
            style={{ display: "inline-flex", alignItems: "center", padding: "16px 32px", borderRadius: "9999px", border: "1px solid rgba(255,255,255,0.2)", color: "inherit", textDecoration: "none" }}
          >
            ← Back to Overview
          </a>
        </div>
      </section>
      <Footer />
    </main>
  );
}
""",
        )

    def _write_work_dynamic_page(self):
        self._text(
            "app/work/[slug]/page.tsx",
            """import React from "react";
import HeaderNavigation from "../../../components/HeaderNavigation";
import Footer from "../../../components/Footer";
import { projects } from "../../../data/projects";

type WorkPageProps = {
  params: Promise<{ slug: string }>;
};

export default async function DynamicWorkPage({ params }: WorkPageProps) {
  const { slug } = await params;
  const proj = projects.find(
    (p: any) => p.slug === slug || p.title.toLowerCase().replace(/\\s+/g, "-") === slug
  );
  const title = proj?.title || slug.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  const desc = proj?.description || `Case study for ${title}.`;
  const image = proj?.image;

  return (
    <main>
      <HeaderNavigation />
      <article style={{ maxWidth: "1200px", margin: "0 auto", padding: "120px 24px 80px", minHeight: "70vh" }}>
        <div style={{ marginBottom: "24px" }}>
          <a href="/" style={{ opacity: 0.6, textDecoration: "none", fontSize: "14px", fontFamily: "var(--font-mono, monospace)" }}>
            ← Back to Overview
          </a>
        </div>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: "clamp(40px, 6vw, 72px)", fontWeight: 700, margin: "0 0 24px 0" }}>
          {title}
        </h1>
        <p style={{ fontFamily: "var(--font-body)", fontSize: "20px", opacity: 0.8, lineHeight: 1.6, maxWidth: "720px" }}>
          {desc}
        </p>
        {image && (
          <img src={image} alt={title} style={{ width: "100%", maxHeight: "640px", objectFit: "cover", borderRadius: "16px", margin: "40px 0" }} />
        )}
      </article>
      <Footer />
    </main>
  );
}
""",
        )

    def _write_work_page(self, route: str):
        slug = route.rstrip("/").split("/")[-1]
        title = self._title_from_slug(slug)
        projects = self.ir.get("data", {}).get("projects", [])
        proj = next((p for p in projects if p.get("slug") == slug or self._slugify(p.get("title", "")) == slug), None)

        proj_title = proj.get("title") if proj else title
        proj_cat = proj.get("category") if proj else "Case Study"
        proj_img = proj.get("image") if proj else None
        proj_desc = proj.get("description") if proj else f"High-fidelity case study for {proj_title}."
        proj_tags = (proj.get("tags") if proj else None) or ["AI / Machine Learning", "Creative Development"]

        img_markup = f'<img src="{proj_img}" alt="{proj_title}" style={{{{ width: "100%", maxHeight: "640px", objectFit: "cover", borderRadius: "16px", margin: "40px 0" }}}} />' if proj_img else ""
        tags_markup = "\n".join([f'          <span key="{i}" style={{{{ padding: "6px 14px", borderRadius: "9999px", background: "rgba(255,255,255,0.08)", fontSize: "14px", fontFamily: "var(--font-mono, monospace)" }}}}>{t}</span>' for i, t in enumerate(proj_tags)])

        self._text(
            f"app/work/{slug}/page.tsx",
            f"""import React from "react";
import HeaderNavigation from "../../../components/HeaderNavigation";
import Footer from "../../../components/Footer";

export default function WorkPage() {{
  return (
    <main>
      <HeaderNavigation />
      <article style={{{{ maxWidth: "1200px", margin: "0 auto", padding: "120px 24px 80px", minHeight: "70vh" }}}}>
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
      <Footer />
    </main>
  );
}}
""",
        )

    def _write_custom_page(self, route: str):
        segment = route.strip("/")
        title = self._title_from_slug(segment)

        self._text(
            f"app/{segment}/page.tsx",
            f"""import HeaderNavigation from "../../components/HeaderNavigation";
import Footer from "../../components/Footer";

export default function {title.replace(' ', '')}Page() {{
  return (
    <main>
      <HeaderNavigation />
      <section className="page-section">
        <h1 style={{{{ fontSize: "clamp(36px, 6vw, 64px)", fontWeight: 800 }}}}>{title}</h1>
      </section>
      <Footer />
    </main>
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

    def _text(
        self,
        relative: str,
        content: str,
    ):
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
