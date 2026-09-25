from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page


from webextractor.config import config
from webextractor.constants import DEFAULT_VIEWPORTS

VIEWPORTS = DEFAULT_VIEWPORTS


class MultiViewportCapture:
    """
    Captures full-page DOM, computed styles, and screenshots across
    configurable responsive breakpoints (Mobile, Tablet, Laptop, Desktop, Widescreen).
    """

    def __init__(
        self,
        output_dir: str | Path,
        viewports: dict[str, dict[str, int]] | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.viewports = viewports or dict(config.viewports)

    async def capture_all(
        self,
        context: BrowserContext,
        url: str,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}

        for device_name, viewport in self.viewports.items():
            page = await context.new_page()
            await page.set_viewport_size(viewport)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                await page.wait_for_timeout(2000)

                # Trigger lazy loaded assets
                await self._scroll(page)
                await page.wait_for_timeout(1000)

                screenshot_path = self.output_dir / "screenshots" / f"{device_name}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path), full_page=True)

                dom_snapshot = await self._extract_dom(page)

                # Mobile interactive state discovery: probe mobile menu if viewport <= 768px
                menu_state = None
                if viewport.get("width", 1440) <= 768:
                    menu_state = await self._probe_mobile_menu(page, device_name)

                results[device_name] = {
                    "viewport": viewport,
                    "screenshot": str(screenshot_path),
                    "dom": dom_snapshot,
                    "menu_state": menu_state,
                }
            finally:
                await page.close()

        # Extract responsive differential rules
        responsive_rules = self._extract_responsive_rules(results)

        return {
            "viewports": results,
            "responsive_rules": responsive_rules,
        }

    async def _probe_mobile_menu(self, page: Page, device_name: str) -> dict[str, Any] | None:
        """Discovers and captures dynamically mounted mobile navigation states."""
        try:
            triggers = await page.query_selector_all(
                "button[aria-label*='menu' i], [aria-expanded], [class*='menu' i], [data-framer-name*='menu' i], [data-framer-name*='nav' i], nav button, header button"
            )
            for trig in triggers:
                if await trig.is_visible():
                    open_ss = self.output_dir / "screenshots" / f"{device_name}_menu_open.png"
                    await trig.click(timeout=3000)
                    await page.wait_for_timeout(600)
                    await page.screenshot(path=str(open_ss), full_page=True)
                    open_dom = await self._extract_dom(page)
                    # Attempt to close back
                    try:
                        await trig.click(timeout=1500)
                        await page.wait_for_timeout(200)
                    except Exception:
                        pass
                    return {
                        "type": "mobile_menu",
                        "screenshot": str(open_ss),
                        "open_dom": open_dom,
                    }
        except Exception:
            pass
        return None

    async def _scroll(self, page: Page) -> None:
        await page.evaluate(
            """
            async () => {
                await new Promise((resolve) => {
                    let total = 0;
                    const distance = 400;
                    const timer = setInterval(() => {
                        window.scrollBy(0, distance);
                        total += distance;
                        if (total >= document.body.scrollHeight) {
                            clearInterval(timer);
                            window.scrollTo(0, 0);
                            resolve();
                        }
                    }, 100);
                });
            }
            """
        )

    async def _extract_dom(self, page: Page) -> dict[str, Any]:
        return await page.evaluate(
            """
            () => {
                function extract(element, depth = 0, path = "0") {
                    if (!element || depth > 20) return null;
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    const attrs = {};
                    if (element.attributes) {
                        for (const attr of element.attributes) {
                            attrs[attr.name] = attr.value;
                        }
                    }
                    const children = [];
                    let idx = 0;
                    for (const child of element.children) {
                        const result = extract(child, depth + 1, `${path}_${idx}`);
                        if (result) children.push(result);
                        idx++;
                    }
                    return {
                        tag: element.tagName.toLowerCase(),
                        id: element.id || null,
                        classes: Array.from(element.classList),
                        role: element.getAttribute("role"),
                        ariaLabel: element.getAttribute("aria-label"),
                        text: element.innerText ? element.innerText.replace(/\\s+/g, ' ').trim().slice(0, 300) : "",
                        visible: style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0,
                        rect: {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        },
                        src: element.src || element.getAttribute("src") || null,
                        poster: element.getAttribute("poster") || null,
                        framerName: element.getAttribute("data-framer-name") || null,
                        framerAppearId: element.getAttribute("data-framer-appear-id") || null,
                        motionId: element.getAttribute("data-motion-id") || null,
                        path: path,
                        attributes: attrs,
                        styles: {
                            display: style.display,
                            position: style.position,
                            top: style.top,
                            right: style.right,
                            bottom: style.bottom,
                            left: style.left,
                            zIndex: style.zIndex,
                            width: style.width,
                            height: style.height,
                            minWidth: style.minWidth,
                            maxWidth: style.maxWidth,
                            minHeight: style.minHeight,
                            maxHeight: style.maxHeight,
                            flexDirection: style.flexDirection,
                            flexWrap: style.flexWrap,
                            justifyContent: style.justifyContent,
                            alignItems: style.alignItems,
                            alignContent: style.alignContent,
                            gap: style.gap,
                            rowGap: style.rowGap,
                            columnGap: style.columnGap,
                            gridTemplateColumns: style.gridTemplateColumns,
                            gridTemplateRows: style.gridTemplateRows,
                            gridColumn: style.gridColumn,
                            gridRow: style.gridRow,
                            overflow: style.overflow,
                            objectFit: style.objectFit,
                            objectPosition: style.objectPosition,
                            aspectRatio: style.aspectRatio,
                            fontFamily: style.fontFamily,
                            fontSize: style.fontSize,
                            fontWeight: style.fontWeight,
                            fontStyle: style.fontStyle,
                            lineHeight: style.lineHeight,
                            letterSpacing: style.letterSpacing,
                            textTransform: style.textTransform,
                            textDecoration: style.textDecorationLine || style.textDecoration,
                            color: style.color,
                            backgroundColor: style.backgroundColor,
                            backgroundImage: style.backgroundImage,
                            borderWidth: style.borderWidth,
                            borderRadius: style.borderRadius,
                            padding: style.padding,
                            margin: style.margin,
                        },
                        children
                    };
                }

                return extract(document.body, 0, "0");
            }
            """
        )

    def _extract_responsive_rules(self, viewports_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Detects layout and style changes across all captured viewports relative to desktop (1440).
        Emits clean CSS selectors and standard breakpoint queries.
        """
        rules: list[dict[str, Any]] = []
        if not viewports_data:
            return rules

        # Flexible desktop DOM resolution (supports 'desktop', 'vp_1440', or closest width to 1440)
        desktop_dom = None
        desktop_key = None

        for k in ("desktop", "vp_1440", "1440"):
            if k in viewports_data and isinstance(viewports_data[k], dict) and viewports_data[k].get("dom"):
                desktop_dom = viewports_data[k]["dom"]
                desktop_key = k
                break

        if not desktop_dom:
            candidates: list[tuple[str, dict[str, Any], int]] = []
            for k, v in viewports_data.items():
                if isinstance(v, dict) and v.get("dom"):
                    vp = v.get("viewport", {})
                    w = vp.get("width", 0)
                    if not w:
                        m = re.search(r"\d+", k)
                        if m:
                            w = int(m.group(0))
                    candidates.append((k, v["dom"], w))
            if candidates:
                candidates.sort(key=lambda item: abs(item[2] - 1440) if item[2] else 9999)
                desktop_key, desktop_dom, _ = candidates[0]

        if not desktop_dom:
            return rules

        def collect_nodes(node: dict[str, Any] | None, acc: list[dict[str, Any]]) -> None:
            if not node:
                return
            acc.append(node)
            for child in node.get("children", []):
                collect_nodes(child, acc)

        desktop_nodes: list[dict[str, Any]] = []
        collect_nodes(desktop_dom, desktop_nodes)

        properties_to_check = (
            "width", "maxWidth", "minWidth", "height", "maxHeight",
            "padding", "margin", "gap", "rowGap", "columnGap",
            "flexDirection", "flexWrap", "display", "alignItems", "justifyContent",
            "gridTemplateColumns", "fontSize", "lineHeight", "letterSpacing",
            "position", "overflow", "visibility"
        )

        seen_rule_keys: set[str] = set()

        for vp_key, vp_val in viewports_data.items():
            if vp_key == desktop_key or not isinstance(vp_val, dict):
                continue

            vp_dom = vp_val.get("dom")
            if not vp_dom:
                continue

            vp_info = vp_val.get("viewport", {})
            w = vp_info.get("width", 0)
            if not w:
                m = re.search(r"\d+", vp_key)
                if m:
                    w = int(m.group(0))

            # Derive standard media query & breakpoint identifier with proper isolation
            if w and w <= 480:
                media_query = "@media (max-width: 768px)"
                bp_name = "mobile"
            elif w and w <= 768:
                media_query = "@media (min-width: 481px) and (max-width: 809.98px)"
                bp_name = "tablet_portrait"
            elif w and w <= 1024:
                media_query = "@media (min-width: 810px) and (max-width: 1024px)"
                bp_name = "tablet"
            elif w and w <= 1280:
                media_query = "@media (min-width: 1025px) and (max-width: 1280px)"
                bp_name = "laptop"
            elif w and w >= 1920:
                media_query = "@media (min-width: 1920px)"
                bp_name = "widescreen"
            elif vp_key in ("mobile", "tablet", "laptop", "widescreen"):
                bp_name = vp_key
                mq_map = {
                    "mobile": "@media (max-width: 768px)",
                    "tablet_portrait": "@media (min-width: 481px) and (max-width: 809.98px)",
                    "tablet": "@media (min-width: 810px) and (max-width: 1024px)",
                    "laptop": "@media (min-width: 1025px) and (max-width: 1280px)",
                    "widescreen": "@media (min-width: 1920px)",
                }
                media_query = mq_map.get(vp_key, "@media (max-width: 768px)")
            else:
                bp_name = vp_key
                media_query = f"@media (max-width: {w}px)" if w else "@media (max-width: 768px)"

            target_nodes: list[dict[str, Any]] = []
            collect_nodes(vp_dom, target_nodes)

            # Build multi-tier index for target nodes
            by_id: dict[str, dict[str, Any]] = {}
            by_appear_id: dict[str, dict[str, Any]] = {}
            by_path: dict[str, dict[str, Any]] = {}
            by_key: dict[str, dict[str, Any]] = {}

            for tn in target_nodes:
                nid = tn.get("id")
                if nid and not str(nid).isdigit():
                    by_id[str(nid)] = tn
                apid = tn.get("framerAppearId") or (tn.get("attributes", {}).get("data-framer-appear-id") if isinstance(tn.get("attributes"), dict) else None)
                if apid:
                    by_appear_id[str(apid)] = tn
                pth = tn.get("path")
                if pth:
                    by_path[str(pth)] = tn
                raw_k = f"{tn.get('tag')}_{tn.get('id')}_{' '.join(tn.get('classes', []))}"
                if raw_k not in by_key:
                    by_key[raw_k] = tn

            for d_node in desktop_nodes:
                nid = str(d_node.get("id")) if d_node.get("id") and not str(d_node.get("id")).isdigit() else None
                apid = d_node.get("framerAppearId") or (d_node.get("attributes", {}).get("data-framer-appear-id") if isinstance(d_node.get("attributes"), dict) else None)
                pth = d_node.get("path")
                raw_k = f"{d_node.get('tag')}_{d_node.get('id')}_{' '.join(d_node.get('classes', []))}"

                # Match by id -> appear_id -> path -> tag_id_classes key
                t_node = None
                if nid and nid in by_id:
                    t_node = by_id[nid]
                elif apid and str(apid) in by_appear_id:
                    t_node = by_appear_id[str(apid)]
                elif pth and str(pth) in by_path:
                    t_node = by_path[str(pth)]
                elif raw_k in by_key:
                    t_node = by_key[raw_k]

                if not t_node:
                    continue

                d_styles = d_node.get("styles", {}) or {}
                t_styles = t_node.get("styles", {}) or {}

                diffs: dict[str, Any] = {}
                for prop in properties_to_check:
                    d_val = d_styles.get(prop)
                    t_val = t_styles.get(prop)
                    if d_val and t_val and d_val != t_val:
                        if d_val in ("auto", "none", "0px") and t_val in ("auto", "none", "0px"):
                            continue
                        diffs[prop] = {
                            "desktop": d_val,
                            bp_name: t_val,
                            "target": t_val,
                        }

                if diffs:
                    node_id = d_node.get("id")
                    appear_id = d_node.get("framerAppearId") or (d_node.get("attributes", {}).get("data-framer-appear-id") if isinstance(d_node.get("attributes"), dict) else None)
                    framer_name = d_node.get("framerName") or (d_node.get("attributes", {}).get("data-framer-name") if isinstance(d_node.get("attributes"), dict) else None)
                    raw_classes = [c for c in d_node.get("classes", []) if not c.startswith("motion-")]
                    classes = [re.sub(r"[^a-zA-Z0-9_-]", "", c) for c in raw_classes if c]
                    classes = [c for c in classes if c]
                    tag = d_node.get("tag", "div")

                    if node_id and not str(node_id).isdigit():
                        clean_selector = f"#{node_id}"
                    elif appear_id:
                        clean_selector = f"[data-framer-appear-id='{appear_id}']"
                    elif classes:
                        clean_selector = "." + ".".join(classes)
                    elif framer_name:
                        clean_selector = f"[data-framer-name='{framer_name}']"
                    elif tag in ("body", "html", "header", "nav", "main", "footer"):
                        clean_selector = tag
                    else:
                        continue

                    rule_id = f"{media_query}_{clean_selector}"
                    if rule_id not in seen_rule_keys:
                        seen_rule_keys.add(rule_id)
                        rules.append({
                            "selector": clean_selector,
                            "raw_key": raw_k,
                            "tag": tag,
                            "media_query": media_query,
                            "breakpoint": bp_name,
                            "diffs": diffs,
                        })

        return rules
