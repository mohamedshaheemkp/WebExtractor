from __future__ import annotations

from typing import Any
from playwright.async_api import Page


class SpatialTreeExtractor:
    """Extracts geometric bounding boxes and layout properties of key elements."""

    EXTRACT_SCRIPT = """() => {
        const selector = [
            'header', 'nav', 'footer', 'main', 'section',
            'video', 'canvas', '[data-framer-name]',
            '[class*="header"]', '[class*="nav"]', '[class*="footer"]',
            '[class*="carousel"]', '[class*="slider"]', '[class*="track"]'
        ].join(', ');

        const elements = Array.from(document.querySelectorAll(selector));
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        return elements.map((el, index) => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            
            // Collect identifiable attributes
            const framerName = el.getAttribute('data-framer-name') || '';
            const id = el.id || '';
            const className = typeof el.className === 'string' ? el.className : '';
            const tag = el.tagName.toLowerCase();

            return {
                index,
                tag,
                id,
                className,
                framerName,
                identifier: framerName || id || (className ? className.split(' ')[0] : `${tag}_${index}`),
                rect: {
                    top: Math.round(rect.top),
                    left: Math.round(rect.left),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    right: Math.round(rect.right),
                    bottom: Math.round(rect.bottom),
                },
                computed: {
                    position: style.position,
                    display: style.display,
                    flexDirection: style.flexDirection,
                    flexWrap: style.flexWrap,
                    overflow: style.overflow,
                    overflowX: style.overflowX,
                    zIndex: style.zIndex,
                    opacity: style.opacity,
                    visibility: style.visibility,
                    transform: style.transform
                },
                isMedia: tag === 'video' || tag === 'canvas',
                videoAttributes: tag === 'video' ? {
                    autoplay: el.hasAttribute('autoplay') || el.autoplay,
                    muted: el.hasAttribute('muted') || el.muted,
                    loop: el.hasAttribute('loop') || el.loop,
                    playsInline: el.hasAttribute('playsinline')
                } : null
            };
        }).filter(item => item.rect.width > 0 && item.rect.height > 0);
    }"""

    @classmethod
    async def capture(cls, page: Page | None) -> list[dict[str, Any]]:
        """Executes the spatial extraction inside the browser context."""
        if page is None:
            return []
        try:
            return await page.evaluate(cls.EXTRACT_SCRIPT)
        except Exception:
            return []

