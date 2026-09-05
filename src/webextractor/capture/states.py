from __future__ import annotations

from typing import Any
from webextractor.model.interaction import Interaction


class StateExplorer:
    """Explores interactive states on a webpage (hover, click, scroll)."""

    @staticmethod
    async def discover_interactions(page: Any) -> list[Interaction]:
        interactions: list[Interaction] = []
        try:
            # Look for buttons, links, and accordion toggles
            elements = await page.query_selector_all("button, a, [role='button'], details")
            for idx, el in enumerate(elements[:15]):
                tag = await el.evaluate("el => el.tagName.toLowerCase()")
                text = (await el.evaluate("el => el.innerText || el.getAttribute('aria-label') || ''")).strip()
                selector = f"{tag}:nth-of-type({idx + 1})"

                interactions.append(
                    Interaction(
                        trigger="click" if tag in ("button", "details") else "hover",
                        selector=selector,
                        action="navigate" if tag == "a" else "toggle_state",
                        description=f"Interaction for {tag} '{text[:30]}'",
                    )
                )
        except Exception:
            pass
        return interactions
