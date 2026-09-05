from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page


VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 375, "height": 812},
}


class MultiViewportCapture:
    """
    Captures full-page DOM, computed styles, and screenshots across
    multiple responsive breakpoints (Desktop, Tablet, Mobile).
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)

    async def capture_all(
        self,
        context: BrowserContext,
        url: str,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}

        for device_name, viewport in VIEWPORTS.items():
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

                results[device_name] = {
                    "viewport": viewport,
                    "screenshot": str(screenshot_path),
                    "dom": dom_snapshot,
                }
            finally:
                await page.close()

        # Extract responsive differential rules
        responsive_rules = self._extract_responsive_rules(results)

        return {
            "viewports": results,
            "responsive_rules": responsive_rules,
        }

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
                function extract(element, depth = 0) {
                    if (!element || depth > 20) return null;
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    const children = [];
                    for (const child of element.children) {
                        const result = extract(child, depth + 1);
                        if (result) children.push(result);
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

                return extract(document.body);
            }
            """
        )

    def _extract_responsive_rules(self, viewports_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Detects style changes between desktop (1440) and mobile (375).
        """
        rules = []
        desktop_dom = viewports_data.get("desktop", {}).get("dom")
        mobile_dom = viewports_data.get("mobile", {}).get("dom")

        if not desktop_dom or not mobile_dom:
            return rules

        def collect_nodes(node, acc):
            if not node:
                return
            key = f"{node.get('tag')}_{node.get('id')}_{' '.join(node.get('classes', []))}"
            if key not in acc:
                acc[key] = node
            for child in node.get("children", []):
                collect_nodes(child, acc)

        desktop_nodes = {}
        mobile_nodes = {}
        collect_nodes(desktop_dom, desktop_nodes)
        collect_nodes(mobile_dom, mobile_nodes)

        for key, d_node in desktop_nodes.items():
            if key in mobile_nodes:
                m_node = mobile_nodes[key]
                d_styles = d_node.get("styles", {})
                m_styles = m_node.get("styles", {})

                diffs = {}
                for prop in ("fontSize", "flexDirection", "display", "padding"):
                    if d_styles.get(prop) and m_styles.get(prop) and d_styles[prop] != m_styles[prop]:
                        diffs[prop] = {
                            "desktop": d_styles[prop],
                            "mobile": m_styles[prop],
                        }

                if diffs:
                    rules.append({
                        "selector": key,
                        "tag": d_node.get("tag"),
                        "text": d_node.get("text", "")[:40],
                        "diffs": diffs,
                    })

        return rules[:30]  # Return top 30 detected responsive rules
