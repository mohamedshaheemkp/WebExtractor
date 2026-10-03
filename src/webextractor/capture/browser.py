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
        screenshot_name: str | None = None,
        id_prefix: str = "wx",
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

        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            # Give client-side applications time to render and any
            # mount/load-triggered animations to settle, so the pre-scroll
            # sample below reflects only elements still waiting to reveal.
            await page.wait_for_timeout(3000)

            # 1. PRE-SCROLL SAMPLE: fingerprint elements that are still
            # faded/offset before anything below the fold has been triggered.
            # These are the candidates for scroll-reveal animations,
            # regardless of which library (Framer, AOS, GSAP, custom
            # IntersectionObserver, etc.) implements them.
            await page.evaluate(
                """
                (prefix) => {
                    const initial = {};
                    let counter = 0;
                    document.querySelectorAll('body *').forEach((el) => {
                        const tag = el.tagName;
                        if (['SCRIPT','STYLE','NOSCRIPT'].includes(tag)) return;
                        // Elements already natively animated by Framer's own
                        // appear-id system are handled by the Framer motion
                        // adapter separately; scanning them here would bake a
                        // second, independent data-motion-id onto the same
                        // element, producing conflicting animation configs
                        // (see analyzer.py's appear_animations merge).
                        if (el.hasAttribute('data-framer-appear-id')) return;
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 2 || rect.height < 2) return;
                        const cs = window.getComputedStyle(el);
                        const opacity = parseFloat(cs.opacity);
                        let tx = 0, ty = 0;
                        try {
                            const m = new DOMMatrixReadOnly(cs.transform);
                            tx = m.m41; ty = m.m42;
                        } catch (e) {}
                        if (opacity < 0.98 || Math.abs(ty) > 4 || Math.abs(tx) > 4) {
                            const id = prefix + '-' + (counter++);
                            el.setAttribute('data-wx-scan-id', id);
                            initial[id] = { opacity, tx, ty };
                        }
                    });
                    window.__wxInitial = initial;
                }
                """,
                id_prefix,
            )

            # Trigger lazy-loaded content and any scroll-linked reveals.
            await self._scroll_page(page)

            await page.wait_for_timeout(1500)

            # 2. POST-SCROLL DIFF: elements whose opacity/transform changed
            # meaningfully were revealed by scroll. Tag them with
            # data-motion-id (the attribute MotionRuntime/DomToJsxEmitter
            # already recognize) so it's baked into the captured HTML/DOM.
            reveal_candidates = await page.evaluate(
                """
                () => {
                    const initial = window.__wxInitial || {};
                    const results = [];
                    Object.keys(initial).forEach((id) => {
                        const el = document.querySelector(`[data-wx-scan-id="${id}"]`);
                        if (!el) return;
                        const cs = window.getComputedStyle(el);
                        const opacity = parseFloat(cs.opacity);
                        let tx = 0, ty = 0;
                        try {
                            const m = new DOMMatrixReadOnly(cs.transform);
                            tx = m.m41; ty = m.m42;
                        } catch (e) {}
                        const before = initial[id];
                        const opacityDelta = Math.abs(opacity - before.opacity);
                        const tyDelta = Math.abs(ty - before.ty);
                        const txDelta = Math.abs(tx - before.tx);
                        if (opacityDelta > 0.15 || tyDelta > 6 || txDelta > 6) {
                            el.setAttribute('data-motion-id', id);
                            let easing = null;
                            let duration = null;
                            if (cs.transitionDuration) {
                                duration = cs.transitionDuration;
                                if (cs.transitionTimingFunction) {
                                    easing = cs.transitionTimingFunction;
                                }
                            }
                            if (!easing && cs.animationTimingFunction) {
                                easing = cs.animationTimingFunction;
                            }
                            results.push({
                                id,
                                initial: { opacity: before.opacity, x: before.tx, y: before.ty },
                                final: { opacity, x: tx, y: ty },
                                duration,
                                easing,
                            });
                        }
                        el.removeAttribute('data-wx-scan-id');
                    });
                    return results;
                }
                """
            )

            # 3. REAL CSS CAPTURE: inline <style> tags plus any stylesheet
            # readable under CORS. Powers keyframe/transition detection that
            # was previously starved of any actual CSS text.
            css_text = await page.evaluate(
                """
                () => {
                    const chunks = [];
                    document.querySelectorAll('style').forEach((s) => {
                        if (s.textContent) chunks.push(s.textContent);
                    });
                    for (const sheet of document.styleSheets) {
                        try {
                            const rules = sheet.cssRules;
                            if (!rules) continue;
                            let text = '';
                            for (const r of rules) text += r.cssText + '\\n';
                            chunks.push(text);
                        } catch (e) {
                            // Cross-origin stylesheet without CORS headers — unreadable, skip.
                        }
                    }
                    return chunks.join('\\n');
                }
                """
            )

            title = await page.title()

            html = await page.content()

            shot_name = screenshot_name or "desktop.png"
            screenshot_path = (
                self.output_dir / "screenshots" / shot_name
            )

            screenshot_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            await page.screenshot(
                path=str(screenshot_path),
                full_page=True,
            )

            discovered_links = await page.evaluate(
                """
                () => {
                    const links = new Set();
                    document.querySelectorAll("a[href]").forEach(el => {
                        const href = el.getAttribute("href");
                        if (href) links.add(href.trim());
                    });
                    document.querySelectorAll("link[rel='canonical']").forEach(el => {
                        const href = el.getAttribute("href");
                        if (href) links.add(href.trim());
                    });
                    return Array.from(links);
                }
                """
            ) or []

            # 4. SPA ROUTER MANIFEST DISCOVERY (e.g. Framer W router table)
            try:
                spa_routes = await page.evaluate(
                    """
                    async () => {
                        const found = [];
                        const scripts = Array.from(document.querySelectorAll('script'))
                            .map(s => s.src)
                            .filter(s => s && (s.includes('script_main') || s.includes('framer') || s.includes('routes')));
                        for (const scriptUrl of scripts) {
                            try {
                                const res = await fetch(scriptUrl);
                                const text = await res.text();
                                const matches = text.matchAll(/path:\\s*[`"'](\\/[^`"']*)['"`]/g);
                                for (const m of matches) {
                                    const p = m[1];
                                    if (p && !p.includes(':') && !found.includes(p)) {
                                        found.push(p);
                                    }
                                }
                            } catch (e) {}
                        }
                        return found;
                    }
                    """
                )
                if spa_routes:
                    discovered_links.extend(spa_routes)
            except Exception:
                pass

            # 5. DYNAMIC NAVIGATION / OVERLAY PROBE
            # Trigger hamburger/navigation toggle so dynamically mounted links and overlay DOM are captured
            overlay_dom = None
            try:
                menu_triggers = await page.query_selector_all(
                    ".framer-zecFa, button[aria-label*='menu' i], [aria-expanded], [class*='menu' i], [data-framer-name*='menu' i], nav [data-highlight], header [data-highlight]"
                )
                for trig in menu_triggers:
                    if await trig.is_visible():
                        box = await trig.bounding_box()
                        if box and box["width"] > 0 and box["height"] > 0:
                            await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                            await page.wait_for_timeout(500)

                            mounted_links = await page.evaluate(
                                """
                                () => {
                                    const links = [];
                                    document.querySelectorAll("a[href]").forEach(el => {
                                        const href = el.getAttribute("href");
                                        if (href) links.push(href.trim());
                                    });
                                    return links;
                                }
                                """
                            )
                            if mounted_links:
                                discovered_links.extend(mounted_links)

                            overlay_dom = await page.evaluate(
                                """
                                () => {
                                    const el = document.getElementById('overlay') ||
                                               document.querySelector('[data-framer-name="Overlay"], .framer-overlay');
                                    if (!el) return null;

                                    function extract(element, depth = 0) {
                                        if (!element || depth > 20) return null;
                                        const rect = element.getBoundingClientRect();
                                        const style = window.getComputedStyle(element);
                                        const children = [];
                                        for (const child of element.children) {
                                            const res = extract(child, depth + 1);
                                            if (res) children.push(res);
                                        }
                                        const attrs = {};
                                        if (element.attributes) {
                                            for (let i = 0; i < element.attributes.length; i++) {
                                                const a = element.attributes[i];
                                                attrs[a.name] = a.value;
                                            }
                                        }
                                        return {
                                            tag: element.tagName.toLowerCase(),
                                            id: element.id || null,
                                            classes: Array.from(element.classList),
                                            rect: {
                                                x: Math.round(rect.x),
                                                y: Math.round(rect.y),
                                                width: Math.round(rect.width),
                                                height: Math.round(rect.height),
                                            },
                                            styles: {
                                                display: style.display,
                                                position: style.position,
                                                zIndex: style.zIndex,
                                                opacity: style.opacity,
                                                transform: style.transform,
                                                backgroundColor: style.backgroundColor,
                                                color: style.color,
                                            },
                                            attributes: attrs,
                                            children,
                                            text: element.innerText ? element.innerText.replace(/\\s+/g, " ").trim().slice(0, 500) : "",
                                        };
                                    }
                                    return extract(el);
                                }
                                """
                            )

                            # Close overlay
                            try:
                                await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                                await page.wait_for_timeout(300)
                            except Exception:
                                pass
                            break
            except Exception:
                pass

            discovered_links = list(dict.fromkeys(discovered_links))

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

                        classes: Array.from(element.classList),


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

                        attributes: (() => {
                            const attrs = {};
                            if (element.attributes) {
                                for (let i = 0; i < element.attributes.length; i++) {
                                    const a = element.attributes[i];
                                    attrs[a.name] = a.value;
                                }
                            }
                            return attrs;
                        })(),

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
                            transition: style.transition,
                            transitionProperty: style.transitionProperty,
                            transitionDuration: style.transitionDuration,
                            transitionTimingFunction: style.transitionTimingFunction,
                            transitionDelay: style.transitionDelay,
                            animationName: style.animationName,
                            animationDuration: style.animationDuration,
                            animationTimingFunction: style.animationTimingFunction,
                            animationDelay: style.animationDelay,
                            animationIterationCount: style.animationIterationCount,
                            transform: style.transform,
                            willChange: style.willChange,
                        },

                        children
                    };
                }


                return extract(document.body);
            }
            """
        )

        finally:
            await page.close()

        return {
            "url": page.url,
            "title": title,
            "html": html,
            "dom": dom_snapshot,
            "requests": network_requests,
            "screenshot": str(screenshot_path),
            "discovered_links": discovered_links or [],
            "overlay": overlay_dom,
            "css": css_text or "",
            "reveal_candidates": reveal_candidates or [],
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
