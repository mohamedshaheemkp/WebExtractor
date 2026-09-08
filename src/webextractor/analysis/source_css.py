from __future__ import annotations

import re
from typing import Any


def _parse_css_blocks(clean_css: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """
    Parses clean CSS text into (normal_rules, at_blocks) using string-aware,
    depth-tracked brace matching. This guarantees all braces are balanced and
    nested at-rules (@supports, @keyframes, etc.) do not corrupt selector parsing.
    """
    i = 0
    length = len(clean_css)
    normal_rules: list[tuple[str, str]] = []
    at_blocks: list[tuple[str, str]] = []

    while i < length:
        while i < length and (clean_css[i].isspace() or clean_css[i] in ";}"):
            i += 1
        if i >= length:
            break

        start = i
        in_str = None
        brace_idx = -1
        semi_idx = -1

        while i < length:
            c = clean_css[i]
            if in_str:
                if c == "\\":
                    i += 2
                    continue
                elif c == in_str:
                    in_str = None
            else:
                if c in ('"', "'"):
                    in_str = c
                elif c == "{":
                    brace_idx = i
                    break
                elif c == ";" and clean_css[start] == "@":
                    semi_idx = i
                    break
            i += 1

        if brace_idx == -1 and semi_idx == -1:
            break

        # Semicolon-terminated at-rule (@import, @charset, etc.)
        if semi_idx != -1 and (brace_idx == -1 or semi_idx < brace_idx):
            i = semi_idx + 1
            continue

        header = clean_css[start:brace_idx].strip()

        # Depth-tracked block matching
        depth = 1
        cur = brace_idx + 1
        in_str = None
        while cur < length and depth > 0:
            c = clean_css[cur]
            if in_str:
                if c == "\\":
                    cur += 2
                    continue
                elif c == in_str:
                    in_str = None
            else:
                if c in ('"', "'"):
                    in_str = c
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
            cur += 1

        body = clean_css[brace_idx + 1 : cur - 1].strip()
        header = header.strip("}; \r\n\t")

        if header.startswith("@"):
            at_blocks.append((header, body))
        else:
            if header and body and "{" not in header and "}" not in header:
                normal_rules.append((header, body))

        i = cur

    return normal_rules, at_blocks


def extract_relevant_css(
    html_content: str,
    referenced_classes: set[str],
    font_families: list[str] | None = None,
    external_css: str = "",
) -> dict[str, Any]:
    """
    Extracts relevant CSS rules, @font-face blocks, and media queries from captured
    HTML/CSS stylesheets based on the classes and fonts actually referenced by the DOM.
    """
    # 1. Collect all CSS text from <style> tags and external sources
    css_sources = []
    if html_content:
        style_tags = re.findall(r"<style[^>]*>(.*?)</style>", html_content, re.DOTALL)
        css_sources.extend(style_tags)
    if external_css:
        css_sources.append(external_css)

    combined_css = "\n".join(css_sources)
    if not combined_css.strip():
        return {"font_faces": [], "class_rules": [], "media_rules": []}

    # 2. Extract @font-face rules
    font_face_blocks: list[str] = []
    target_families = set()
    if font_families:
        for f in font_families:
            target_families.add(f.lower().strip("\"'"))

    for match in re.finditer(r"@font-face\s*\{([^}]+)\}", combined_css, re.IGNORECASE):
        block = match.group(0).strip()
        body = match.group(1)
        if target_families:
            fam_match = re.search(r"font-family\s*:\s*([^;]+);", body, re.IGNORECASE)
            if fam_match:
                fam_val = fam_match.group(1).lower().strip("\"' \t\r\n")
                if any(tf in fam_val for tf in target_families):
                    font_face_blocks.append(block)
            else:
                font_face_blocks.append(block)
        else:
            font_face_blocks.append(block)

    # 3. Remove comments safely preserving strings
    clean_chars = []
    i = 0
    length = len(combined_css)
    in_str = None
    while i < length:
        c = combined_css[i]
        if in_str:
            clean_chars.append(c)
            if c == "\\":
                if i + 1 < length:
                    clean_chars.append(combined_css[i + 1])
                    i += 2
                    continue
            elif c == in_str:
                in_str = None
            i += 1
        else:
            if c == "/" and i + 1 < length and combined_css[i + 1] == "*":
                end_comment = combined_css.find("*/", i + 2)
                if end_comment == -1:
                    break
                i = end_comment + 2
                continue
            elif c in ('"', "'"):
                in_str = c
                clean_chars.append(c)
                i += 1
            else:
                clean_chars.append(c)
                i += 1

    clean_css = "".join(clean_chars)

    # 4. Parse statements into top-level rules and grouping at-rules
    top_level_rules, at_blocks = _parse_css_blocks(clean_css)

    def selector_matches_classes(sel: str) -> bool:
        classes_in_sel = re.findall(r"\.([a-zA-Z0-9_\-]+)", sel)
        for c in classes_in_sel:
            if c in referenced_classes:
                return True
        return False

    relevant_class_rules: list[str] = []
    seen_rules = set()

    for sel, body in top_level_rules:
        sub_selectors = [s.strip() for s in sel.split(",")]
        matching_sub = [s.strip("}; \r\n\t") for s in sub_selectors if selector_matches_classes(s)]
        matching_sub = [s for s in matching_sub if s and "{" not in s and "}" not in s]
        if matching_sub:
            final_sel = ", ".join(matching_sub)
            rule_str = f"{final_sel} {{\n  {body}\n}}"
            if rule_str not in seen_rules:
                seen_rules.add(rule_str)
                relevant_class_rules.append(rule_str)

    # 5. Filter @media rules using the same block parser
    relevant_media_rules: list[str] = []
    for media_hdr, inner_css in at_blocks:
        if not media_hdr.startswith("@media"):
            continue
        inner_rules, _ = _parse_css_blocks(inner_css)
        formatted_inner: list[str] = []
        for sel, body in inner_rules:
            sub_selectors = [s.strip() for s in sel.split(",")]
            matching_sub = [s.strip("}; \r\n\t") for s in sub_selectors if selector_matches_classes(s)]
            matching_sub = [s for s in matching_sub if s and "{" not in s and "}" not in s]
            if matching_sub:
                final_sel = ", ".join(matching_sub)
                formatted_inner.append(f"  {final_sel} {{\n    {body}\n  }}")

        if formatted_inner:
            media_rule_str = f"{media_hdr} {{\n" + "\n".join(formatted_inner) + "\n}"
            relevant_media_rules.append(media_rule_str)

    return {
        "font_faces": font_face_blocks,
        "class_rules": relevant_class_rules,
        "media_rules": relevant_media_rules,
    }
