from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)


class BrowserCapture:
    """
    Launches a real Chromium browser and captures a rendered website.
    """

    def __init__(
        self,
        output_dir: str | Path,
        viewport_width: int = 1440,
        viewport_height: int = 900,
    ):
        self.output_dir = Path(output_dir)
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height

        self.playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None

    async def start(self) -> None:
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=True,
        )

        self.context = await self.browser.new_context(
            viewport={
                "width": self.viewport_width,
                "height": self.viewport_height,
            },
            device_scale_factor=1,
        )

    async def capture(
        self,
        url: str,
    ) -> dict[str, Any]:

        if self.context is None:
            raise RuntimeError("Browser has not been started.")

        page = await self.context.new_page()

        network_requests: list[dict[str, Any]] = []

        page.on(
            "request",
            lambda request: network_requests.append(
                {
                    "url": request.url,
                    "method": request.method,
                    "resource_type": request.resource_type,
                }
            ),
        )

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        # Give client-side applications time to render.
        await page.wait_for_timeout(3000)

        # Trigger lazy-loaded content.
        await self._scroll_page(page)

        await page.wait_for_timeout(1500)

        title = await page.title()

        html = await page.content()

        screenshot_path = (
            self.output_dir / "screenshots" / "desktop.png"
        )

        screenshot_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        await page.screenshot(
            path=str(screenshot_path),
            full_page=True,
        )

        dom_snapshot = await page.evaluate(
            """
            () => {
                function extract(element, depth = 0) {
                    if (!element || depth > 20) {
                        return null;
                    }

                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);

                    const children = [];

                    for (const child of element.children) {
                        const result = extract(
                            child,
                            depth + 1
                        );

                        if (result) {
                            children.push(result);
                        }
                    }

                    return {
                        tag: element.tagName.toLowerCase(),

                        id: element.id || null,

                        classes: Array.from(
                            element.classList
                        ),

                        role:
                            element.getAttribute("role"),

                        ariaLabel:
                            element.getAttribute(
                                "aria-label"
                            ),

                        text:
                            element.innerText
                                ? element.innerText
                                    .replace(/\\s+/g, " ")
                                    .trim()
                                    .slice(0, 500)
                                : "",

                        visible:
                            style.display !== "none" &&
                            style.visibility !== "hidden" &&
                            rect.width > 0 &&
                            rect.height > 0,

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
                            margin: style.margin,
                            padding: style.padding,
                            borderWidth: style.borderWidth,
                            borderRadius: style.borderRadius,
                            color: style.color,
                            backgroundColor: style.backgroundColor,
                            backgroundImage: style.backgroundImage,
                            fontFamily: style.fontFamily,
                            fontSize: style.fontSize,
                            fontWeight: style.fontWeight,
                            fontStyle: style.fontStyle,
                            lineHeight: style.lineHeight,
                            letterSpacing: style.letterSpacing,
                            textTransform: style.textTransform,
                            textDecoration: style.textDecorationLine || style.textDecoration,
                        },

                        children
                    };
                }


                return extract(document.body);
            }
            """
        )

        return {
            "url": page.url,
            "title": title,
            "html": html,
            "dom": dom_snapshot,
            "requests": network_requests,
            "screenshot": str(screenshot_path),
            "viewport": {
                "width": self.viewport_width,
                "height": self.viewport_height,
            },
        }

    async def _scroll_page(self, page: Page) -> None:
        await page.evaluate(
            """
            async () => {
                await new Promise((resolve) => {
                    let total = 0;
                    const distance = 500;

                    const timer = setInterval(() => {
                        window.scrollBy(0, distance);
                        total += distance;

                        if (
                            total >= document.body.scrollHeight
                        ) {
                            clearInterval(timer);
                            window.scrollTo(0, 0);
                            resolve();
                        }
                    }, 100);
                });
            }
            """
        )

    async def close(self) -> None:
        if self.context:
            await self.context.close()

        if self.browser:
            await self.browser.close()

        if self.playwright:
            await self.playwright.stop()
