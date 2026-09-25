from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path
from typing import Any


class StaticProjectGenerator:
    """
    Generates a zero-dependency, production-ready static website (HTML5, CSS3, Vanilla JS)
    from canonical SiteIR.
    Requires NO Node.js, npm, or build tools to run.
    """

    SELF_CLOSING = {
        "img", "br", "hr", "input", "source", "meta", "link",
        "circle", "rect", "path", "line", "polygon", "polyline",
    }

    def __init__(self, site_ir: dict[str, Any] | Any, output_dir: str | Path):
        if hasattr(site_ir, "to_dict"):
            self.ir = site_ir.to_dict()
        elif hasattr(site_ir, "model_dump"):
            self.ir = site_ir.model_dump()
        elif isinstance(site_ir, dict):
            self.ir = site_ir
        else:
            self.ir = dict(site_ir)

        self.output = Path(output_dir)
        self.asset_bindings = self.ir.get("asset_bindings", [])
        # Map source URLs and public/ paths to static assets/ paths
        self.asset_map: dict[str, str] = {}
        for b in self.asset_bindings:
            src = b.get("source_url")
            lp = b.get("local_path")
            if lp:
                clean_lp = lp.lstrip("/").replace("public/", "assets/")
                if not clean_lp.startswith("assets/"):
                    clean_lp = f"assets/{clean_lp}"
                if src:
                    self.asset_map[src] = clean_lp
                self.asset_map[lp] = clean_lp
            for v in b.get("variants", []):
                v_lp = v.get("local_path")
                if v_lp:
                    clean_v = v_lp.lstrip("/").replace("public/", "assets/")
                    if not clean_v.startswith("assets/"):
                        clean_v = f"assets/{clean_v}"
                    self.asset_map[v_lp] = clean_v

    def generate(self) -> Path:
        self._create_structure()
        self._copy_and_organize_assets()
        self._write_tokens()
        self._write_styles()
        self._write_script()
        self._write_pages()
        self._write_readme()
        return self.output

    def _create_structure(self) -> None:
        for folder in ["css", "js", "assets", "assets/images", "assets/fonts", "assets/videos"]:
            (self.output / folder).mkdir(parents=True, exist_ok=True)

    def _copy_and_organize_assets(self) -> None:
        """Copies any existing public/ assets or cached files to the static assets/ directory."""
        public_dir = self.output / "public"
        if not public_dir.exists():
            sibling = self.output.parent / self.output.name.replace("-html", "") / "public"
            if sibling.exists():
                public_dir = sibling
        assets_dir = self.output / "assets"
        if public_dir.exists() and public_dir.is_dir():
            for item in public_dir.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(public_dir)
                    dest = assets_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists() or dest.stat().st_size != item.stat().st_size:
                        shutil.copy2(item, dest)

    def _resolve_asset_url(self, raw_url: str | None) -> str:
        if not raw_url:
            return ""
        if raw_url in self.asset_map:
            return self.asset_map[raw_url]
        for k, v in self.asset_map.items():
            if k and (raw_url == k or raw_url.endswith(k) or (k in raw_url)):
                return v
        if raw_url.startswith("public/"):
            return f"assets/{raw_url[7:]}"
        if raw_url.startswith("/"):
            return f"assets{raw_url}"
        return raw_url

    def _find_bound_variants(self, raw_src: str | None) -> list[dict[str, Any]]:
        if not raw_src:
            return []
        clean_src = raw_src.split("?")[0]
        for b in self.asset_bindings:
            s_url = b.get("source_url", "")
            if s_url == raw_src or s_url.split("?")[0] == clean_src:
                return b.get("variants", [])
        return []

    def _write_tokens(self) -> None:
        design = self.ir.get("design_system", {})
        colors = design.get("colors", {})
        radii = design.get("radii", {})
        typography = self.ir.get("typography", {})
        roles = typography.get("roles", {})
        layout = self.ir.get("layout", {})
        layout_tokens = layout.get("tokens", {})

        lines = [":root {"]
        # Colors
        for name, val in colors.items():
            clean_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name).lower()
            lines.append(f"  --color-{clean_name}: {val};")

        # Radii
        for name, val in radii.items():
            clean_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name).lower()
            lines.append(f"  --radius-{clean_name}: {val};")

        # Layout
        max_w = layout_tokens.get("container_max_width", "1280px")
        padding = layout_tokens.get("container_padding", "80px 48px")
        lines.append(f"  --container-max-width: {max_w};")
        lines.append(f"  --container-padding: {padding};")

        # Fonts
        font_families = typography.get("font_families", [])
        display_fam = font_families[0]["name"] if font_families else "system-ui, -apple-system, sans-serif"
        body_fam = font_families[1]["name"] if len(font_families) > 1 else display_fam
        lines.append(f"  --font-display: '{display_fam}', system-ui, sans-serif;")
        lines.append(f"  --font-body: '{body_fam}', system-ui, sans-serif;")
        lines.append("}\n")

        (self.output / "css" / "tokens.css").write_text("\n".join(lines), encoding="utf-8")

    def _write_styles(self) -> None:
        component_styles = self.ir.get("component_styles", {})
        source_rules = component_styles.get("source_rules", {})
        class_rules = source_rules.get("class_rules", [])
        media_rules = source_rules.get("media_rules", [])
        keyframes = source_rules.get("keyframes", [])

        css_lines = [
            '/* WebExtractor — Static Production Stylesheet */',
            '@import "./tokens.css";',
            '',
            '*, *::before, *::after {',
            '  box-sizing: border-box;',
            '  margin: 0;',
            '  padding: 0;',
            '}',
            '',
            'html {',
            '  scroll-behavior: smooth;',
            '}',
            '',
            'body {',
            '  background: var(--color-background, #080808);',
            '  color: var(--color-foreground, #f5f5f5);',
            '  font-family: var(--font-body, system-ui, -apple-system, sans-serif);',
            '  line-height: 1.6;',
            '}',
            '',
            'img, video, svg {',
            '  display: block;',
            '  max-width: 100%;',
            '  height: auto;',
            '}',
            '',
            'a {',
            '  color: inherit;',
            '  text-decoration: none;',
            '}',
            '',
            'button {',
            '  font: inherit;',
            '  cursor: pointer;',
            '  border: none;',
            '  background: none;',
            '}',
            '',
            '/* Layout Container */',
            '.wx-container {',
            '  width: 100%;',
            '  max-width: var(--container-max-width, 1280px);',
            '  margin: 0 auto;',
            '  padding: 0 24px;',
            '}',
        ]

        animations = self.ir.get("animations", {})
        dur = animations.get("default_transition_duration", 0.7)
        easing = animations.get("timing_function") or animations.get("default_timing_function") or animations.get("default_easing") or "cubic-bezier(0.16, 1, 0.3, 1)"

        css_lines.extend([
            '',
            '/* Reveal Animation Classes */',
            '.wx-reveal {',
            '  opacity: 0;',
            '  transform: translateY(24px);',
            f'  transition: opacity {dur}s {easing}, transform {dur}s {easing};',
            '}',
            '',
            '.wx-reveal.wx-revealed {',
            '  opacity: 1;',
            '  transform: translateY(0);',
            '}',
        ])

        element_transitions = animations.get("element_transitions", {})
        if element_transitions:
            css_lines.append('\n/* Element Transitions (Preserved Curves) */')
            for sel, t_cfg in element_transitions.items():
                tf = t_cfg.get("timing_function") or t_cfg.get("easing") or t_cfg.get("ease") or easing
                d_val = t_cfg.get("duration") if t_cfg.get("duration") is not None else dur
                if tf:
                    css_lines.extend([
                        f'{sel} {{',
                        f'  transition: all {d_val}s {tf} !important;',
                        f'}}',
                    ])

        if class_rules:
            css_lines.append('\n/* Extracted Source Styles */')
            css_lines.extend(class_rules)

        if keyframes:
            css_lines.append('\n/* Extracted Keyframes */')
            css_lines.extend(keyframes)

        # Process authoritative responsive rules from SiteIR
        responsive_rules = self.ir.get("responsive_rules", [])
        media_blocks: dict[str, list[str]] = {}

        for r in responsive_rules:
            mq = r.get("media_query") or "@media (max-width: 768px)"
            sel = r.get("selector")
            if not sel or not r.get("diffs"):
                continue

            # Convert raw synthetic keys like div_None_class into valid CSS classes if needed
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
                media_blocks.setdefault(mq, []).append(f"  {sel} {{\n" + "\n".join(prop_lines) + "\n  }")

        for mq, rules in sorted(media_blocks.items()):
            css_lines.append(f"\n/* Responsive Breakpoint: {mq} */")
            css_lines.append(f"{mq} {{")
            css_lines.extend(rules)
            css_lines.append("}")

        if media_rules:
            css_lines.append("\n/* Source Extracted Responsive Media Rules */")
            css_lines.extend(media_rules)

        (self.output / "css").mkdir(parents=True, exist_ok=True)
        (self.output / "css" / "styles.css").write_text("\n".join(css_lines), encoding="utf-8")

    def _write_script(self) -> None:
        js_content = """\
/**
 * WebExtractor — Static Interaction & Motion Runtime
 */
(function () {
  'use strict';

  // 1. Intersection Observer for Scroll Reveals
  const revealElements = document.querySelectorAll('.wx-reveal, [data-motion-id]');
  if ('IntersectionObserver' in window && revealElements.length > 0) {
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('wx-revealed');
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });

    revealElements.forEach(el => observer.observe(el));
  } else {
    revealElements.forEach(el => el.classList.add('wx-revealed'));
  }

  // 2. Mobile Menu Toggle Support
  const menuButtons = document.querySelectorAll('[aria-expanded], .menu-toggle, [data-menu-toggle]');
  menuButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!expanded));
      const targetId = btn.getAttribute('aria-controls') || btn.getAttribute('data-target');
      if (targetId) {
        const target = document.getElementById(targetId);
        if (target) target.classList.toggle('active');
      }
    });
  });

  // 3. Smooth Anchor Scrolling
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const targetId = this.getAttribute('href').substring(1);
      if (!targetId) return;
      const target = document.getElementById(targetId);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
})();
"""
        (self.output / "js" / "app.js").write_text(js_content, encoding="utf-8")

    def _node_to_html(self, node: dict[str, Any] | None, depth: int = 2) -> str:
        if not node:
            return ""

        indent = "  " * depth
        tag = (node.get("tag") or "div").lower()
        if tag == "body":
            tag = "div"

        attrs = node.get("attributes", {}) or {}
        classes = list(node.get("classes", []))
        node_id = node.get("id")

        # Rewrite asset paths in attributes
        attr_strs = []
        if node_id:
            attr_strs.append(f'id="{html.escape(str(node_id))}"')

        # Collect classes
        class_str = " ".join(classes).strip()
        if class_str:
            attr_strs.append(f'class="{html.escape(class_str)}"')

        has_style = False
        has_srcset = False
        for k, v in attrs.items():
            k_low = k.lower()
            if k_low in ("id", "class", "classname"):
                continue
            if k_low == "style":
                has_style = True
                v_str = self._resolve_asset_url(str(v))
                attr_strs.append(f'style="{html.escape(v_str)}"')
                continue
            v_str = str(v)
            if k_low == "srcset":
                has_srcset = True
                parts = [p.strip() for p in v_str.split(",") if p.strip()]
                resolved_parts = []
                for p in parts:
                    sub = p.split()
                    if sub:
                        res_url = self._resolve_asset_url(sub[0])
                        w_desc = f" {sub[1]}" if len(sub) > 1 else ""
                        resolved_parts.append(f"{res_url}{w_desc}")
                attr_strs.append(f'srcset="{html.escape(", ".join(resolved_parts))}"')
                continue
            if k_low in ("src", "href", "poster"):
                v_str = self._resolve_asset_url(v_str)
            attr_strs.append(f'{k}="{html.escape(v_str)}"')

        # If img has genuine variants and no explicit srcset, emit evidence-based srcset
        if tag == "img" and not has_srcset:
            img_src = attrs.get("src") or node.get("src")
            if img_src:
                variants = self._find_bound_variants(str(img_src))
                if len(variants) > 1:
                    cand_strs = []
                    for v in variants:
                        v_loc = v.get("local_path")
                        v_w = v.get("width")
                        if v_loc and v_w:
                            res_loc = self._resolve_asset_url(v_loc)
                            cand_strs.append(f"{res_loc} {v_w}w")
                    if cand_strs:
                        attr_strs.append(f'srcset="{html.escape(", ".join(cand_strs))}"')
                        if "sizes" not in [ak.lower() for ak in attrs.keys()]:
                            attr_strs.append('sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"')

        # Only if node had no explicit style attribute and has explicit motion styles (opacity or transform), preserve them
        if not has_style:
            styles = node.get("styles", {})
            if styles and isinstance(styles, dict):
                motion_parts = []
                op = styles.get("opacity")
                tf = styles.get("transform")
                if op is not None and str(op) not in ("1", "1.0", "normal"):
                    motion_parts.append(f"opacity: {op}")
                if tf and tf not in ("none", "matrix(1, 0, 0, 1, 0, 0)"):
                    motion_parts.append(f"transform: {tf}")
                if motion_parts:
                    attr_strs.append(f'style="{html.escape("; ".join(motion_parts))}"')

        open_tag = f"{indent}<{tag}" + ((" " + " ".join(attr_strs)) if attr_strs else "") + ">"

        if tag in self.SELF_CLOSING:
            return open_tag

        children = node.get("children", [])
        text = node.get("text", "")

        if not children and text:
            return f"{open_tag}{html.escape(text)}</{tag}>"

        inner_htmls = []
        for child in children:
            child_html = self._node_to_html(child, depth + 1)
            if child_html:
                inner_htmls.append(child_html)

        if not inner_htmls:
            return f"{open_tag}</{tag}>"

        return f"{open_tag}\n" + "\n".join(inner_htmls) + f"\n{indent}</{tag}>"

    def _write_pages(self) -> None:
        title = self.ir.get("metadata", {}).get("title") or "Reconstructed Website"
        pages = self.ir.get("pages", [])

        if not pages:
            # Generate single home page from root components
            pages = [{"route": "/", "title": title}]

        for page in pages:
            route = page.get("route", "/")
            page_title = page.get("title") or title
            page_dom = page.get("dom") or self.ir.get("components")

            # Determine destination filename
            if route in ("/", ""):
                dest_file = self.output / "index.html"
            else:
                slug = route.strip("/").replace("/", "_")
                dest_file = self.output / f"{slug}.html"

            body_content = ""
            if page_dom:
                body_content = self._node_to_html(page_dom, depth=2)
            else:
                body_content = '    <div class="wx-container"><p>Content reconstructed from source.</p></div>'

            html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(page_title)}</title>
  <link rel="stylesheet" href="./css/tokens.css">
  <link rel="stylesheet" href="./css/styles.css">
</head>
<body>
{body_content}
  <script src="./js/app.js"></script>
</body>
</html>
"""
            dest_file.write_text(html_doc, encoding="utf-8")

    def _write_readme(self) -> None:
        readme_content = """# Reconstructed Static Website

This project is a standalone, zero-dependency static export generated by **WebExtractor**.

## How to Run
- Double click `index.html` to open directly in any modern browser.
- Or run a local HTTP server:
  ```bash
  npx serve .
  # or
  python -m http.server 3000
  ```
"""
        (self.output / "README.md").write_text(readme_content, encoding="utf-8")
