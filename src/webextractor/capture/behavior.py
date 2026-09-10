from __future__ import annotations

import asyncio
import re
from typing import Any
from webextractor.model.interaction import ActionSpec, InteractionIR, TriggerSpec


class BehaviorProbe:
    """
    Universal Browser Behavioral Capture Probe.
    Actively observes, interacts with, and diffs page states to extract
    ground-truth behavioral evidence directly from runtime execution.
    """

    def __init__(self, settle_time_ms: int = 400):
        self.settle_time_ms = settle_time_ms

    async def probe_page(self, page: Any, max_candidates: int = 12) -> list[dict[str, Any]]:
        """
        Executes active behavioral exploration on a live Playwright page.
        Returns a list of discovered InteractionIR dicts.
        """
        interactions: list[dict[str, Any]] = []
        try:
            candidates = await self.discover_interactive_elements(page, max_candidates=max_candidates)
            if not candidates:
                return interactions

            for idx, cand in enumerate(candidates):
                selector = cand.get("selector")
                if not selector:
                    continue

                # 1. Capture state before interaction
                before_state = await self.snapshot_state(page)

                # 2. Check for continuous motion on candidate before click
                continuous_motion = await self._detect_continuous_motion(page, selector)

                # 3. Perform click interaction
                clicked = await self._safe_click(page, selector)
                if not clicked:
                    continue

                await self.wait_for_settle(page)

                # 4. Capture state after click
                after_state = await self.snapshot_state(page)

                # 5. Diff states
                state_diff = self.compare_states(before_state, after_state, trigger_selector=selector)

                if state_diff.get("has_change"):
                    # Check toggleability by clicking again
                    await self._safe_click(page, selector)
                    await self.wait_for_settle(page)
                    toggle_after_state = await self.snapshot_state(page)
                    toggle_diff = self.compare_states(after_state, toggle_after_state, trigger_selector=selector)
                    is_toggle = toggle_diff.get("has_change") and not self.compare_states(before_state, toggle_after_state, selector).get("has_change")

                    # Extract structured InteractionIR
                    interaction = self.extract_interaction(
                        interaction_id=f"interaction-{idx + 1:03d}",
                        trigger_type="click",
                        candidate=cand,
                        before_state=before_state,
                        after_state=after_state,
                        state_diff=state_diff,
                        is_toggle=is_toggle,
                        continuous_motion=continuous_motion,
                    )
                    interactions.append(interaction.to_dict())
                else:
                    # If click had no DOM change, check hover behavior
                    hover_diff = await self._probe_hover(page, selector)
                    if hover_diff and hover_diff.get("has_change"):
                        interaction = self.extract_interaction(
                            interaction_id=f"interaction-hover-{idx + 1:03d}",
                            trigger_type="hover",
                            candidate=cand,
                            before_state=hover_diff.get("before", {}),
                            after_state=hover_diff.get("after", {}),
                            state_diff=hover_diff,
                            is_toggle=False,
                            continuous_motion=continuous_motion,
                        )
                        interactions.append(interaction.to_dict())

        except Exception as e:
            # Fallback gracefully if browser interaction encounters an error
            pass

        return interactions

    async def discover_interactive_elements(self, page: Any, max_candidates: int = 15) -> list[dict[str, Any]]:
        """
        Discovers candidate interactive elements using structural and behavioral cues:
        buttons, links, triggers, cursor:pointer elements, ARIA controls, custom indicators.
        """
        script = """
        () => {
            const candidates = [];
            const seen = new Set();

            function isDevOrEditorElement(el) {
                if (!el || !(el instanceof Element)) return false;
                const id = el.id || '';
                const cls = typeof el.className === 'string' ? el.className : '';
                const framerName = el.getAttribute('data-framer-name') || '';
                const combined = (id + ' ' + cls + ' ' + framerName).toLowerCase();
                if (/__framer-(editor|badge)/i.test(combined)) return true;
                if (/__next-|webpack|vite-overlay|__react_devtools/i.test(combined)) return true;
                if (/(editorbar|edit-mode|dev-tools|debug-bar)/i.test(combined)) return true;
                if (el.closest('[id*="editorbar"], [class*="editorbar"], [id*="__framer-badge"], [id*="webpack"]')) return true;
                return false;
            }

            function getCssPath(el) {
                if (!(el instanceof Element)) return '';
                if (isDevOrEditorElement(el)) return '';
                if (el.id) {
                    return /^[a-zA-Z_][a-zA-Z0-9_-]*$/.test(el.id) ? ('#' + el.id) : (`[id="${el.id.replace(/"/g, '\\\\\\"')}"]`);
                }
                
                const framerName = el.getAttribute('data-framer-name');
                if (framerName) return `[data-framer-name="${framerName.replace(/"/g, '\\\\\\"')}"]`;

                const ariaLabel = el.getAttribute('aria-label');
                if (ariaLabel) return `[aria-label="${ariaLabel.replace(/"/g, '\\\\\\"')}"]`;

                let path = [];
                while (el && el.nodeType === Node.ELEMENT_NODE && el.tagName.toLowerCase() !== 'body') {
                    let selector = el.nodeName.toLowerCase();
                    if (el.className && typeof el.className === 'string' && el.className.trim()) {
                        const firstClass = el.className.trim().split(/\\s+/)[0];
                        if (firstClass && !firstClass.startsWith('_') && !/^\\d/.test(firstClass)) {
                            selector += '.' + (typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(firstClass) : firstClass);
                        }
                    }
                    let sib = el, nth = 1;
                    while (sib = sib.previousElementSibling) {
                        if (sib.nodeName.toLowerCase() === el.nodeName.toLowerCase()) nth++;
                    }
                    if (nth > 1) selector += `:nth-of-type(${nth})`;
                    path.unshift(selector);
                    el = el.parentElement;
                }
                return path.join(' > ');
            }

            // High-priority candidate queries
            const elements = document.querySelectorAll(
                'button, [role="button"], a[href^="#"], [aria-expanded], [aria-controls], ' +
                '[data-framer-name*="Menu" i], [data-framer-name*="Nav" i], [data-framer-name*="Trigger" i], ' +
                '[data-framer-name*="Button" i], [data-interaction-trigger], [tabindex="0"]'
            );

            elements.forEach(el => {
                if (isDevOrEditorElement(el)) return;
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden') {
                    const sel = getCssPath(el);
                    if (sel && !seen.has(sel)) {
                        seen.add(sel);
                        candidates.push({
                            selector: sel,
                            tag: el.tagName.toLowerCase(),
                            text: (el.innerText || '').trim().slice(0, 50),
                            id: el.id || null,
                            ariaExpanded: el.getAttribute('aria-expanded'),
                            ariaControls: el.getAttribute('aria-controls'),
                            classes: Array.from(el.classList),
                            rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                            isCenterOrFixed: style.position === 'fixed' || style.position === 'sticky' || (rect.y < 300 && rect.x > 300),
                        });
                    }
                }
            });

            // Fallback: check fixed or pointer elements if few candidates found
            if (candidates.length < 5) {
                const all = document.querySelectorAll('div, span, nav, header');
                for (const el of all) {
                    if (isDevOrEditorElement(el)) continue;
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    if (style.cursor === 'pointer' && rect.width > 12 && rect.height > 12 && rect.width < 500 && rect.height < 500) {
                        const sel = getCssPath(el);
                        if (sel && !seen.has(sel)) {
                            seen.add(sel);
                            candidates.push({
                                selector: sel,
                                tag: el.tagName.toLowerCase(),
                                text: (el.innerText || '').trim().slice(0, 50),
                                id: el.id || null,
                                ariaExpanded: el.getAttribute('aria-expanded'),
                                ariaControls: el.getAttribute('aria-controls'),
                                classes: Array.from(el.classList),
                                rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                                isCenterOrFixed: style.position === 'fixed',
                            });
                        }
                    }
                }
            }

            return candidates;
        }
        """
        res = await page.evaluate(script)
        return res[:max_candidates] if isinstance(res, list) else []

    async def snapshot_state(self, page: Any) -> dict[str, Any]:
        """
        Captures state snapshot of current DOM:
        visible text, computed styles of key containers, visibility, opacity, transform, links.
        """
        script = """
        () => {
            const snapshot = {
                links: [],
                visibleElements: {},
                ariaStates: {},
            };

            // Collect all visible links
            document.querySelectorAll('a[href]').forEach(a => {
                const rect = a.getBoundingClientRect();
                const style = window.getComputedStyle(a);
                const isVis = style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 && parseFloat(style.opacity || '1') > 0.05;
                snapshot.links.push({
                    href: a.getAttribute('href') || '',
                    text: (a.innerText || '').trim(),
                    visible: isVis,
                });
            });

            // Inspect elements with ids, classes or framer attributes
            const nodes = document.querySelectorAll('header, nav, main, aside, [id], [data-framer-name], [aria-expanded], [aria-hidden], ul, ol');
            nodes.forEach(el => {
                if (isDevOrEditorElement(el)) return;
                const sel = getCssPath(el);
                const idOrKey = sel || (el.id ? ('#' + CSS.escape(el.id)) : (el.getAttribute('data-framer-name') ? `[data-framer-name="${el.getAttribute('data-framer-name')}"]` : (el.tagName.toLowerCase() + '.' + Array.from(el.classList).slice(0, 2).join('.'))));
                if (idOrKey) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    const isVis = style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 && parseFloat(style.opacity || '1') > 0.05;
                    snapshot.visibleElements[idOrKey] = {
                        tag: el.tagName.toLowerCase(),
                        selector: sel || idOrKey,
                        text: (el.innerText || '').trim().slice(0, 100),
                        visible: isVis,
                        display: style.display,
                        visibility: style.visibility,
                        opacity: parseFloat(style.opacity || '1'),
                        transform: style.transform,
                        pointerEvents: style.pointerEvents,
                        rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
                        ariaExpanded: el.getAttribute('aria-expanded'),
                        ariaHidden: el.getAttribute('aria-hidden'),
                    };
                }
            });

            return snapshot;
        }
        """
        return await page.evaluate(script)

    async def wait_for_settle(self, page: Any) -> None:
        """Waits for layout recalculations, animations, and transitions to settle."""
        try:
            await page.wait_for_timeout(self.settle_time_ms)
        except Exception:
            await asyncio.sleep(self.settle_time_ms / 1000.0)

    def compare_states(
        self,
        before_state: dict[str, Any],
        after_state: dict[str, Any],
        trigger_selector: str = "",
    ) -> dict[str, Any]:
        """
        Diffs two state snapshots to extract behavioral changes:
        newly visible navigation links, visibility changes, opacity/transform shifts.
        """
        before_links = before_state.get("links", [])
        after_links = after_state.get("links", [])

        # 1. Detect navigation links revealed (keyed by (href, text) to detect new links even with shared href)
        before_vis_links = {
            (l.get("href"), (l.get("text") or "").strip().lower())
            for l in before_links
            if l.get("visible") and l.get("href")
        }
        after_vis_links = [
            l for l in after_links
            if l.get("visible") and l.get("href")
        ]

        revealed_links: list[dict[str, str]] = []
        seen_revealed = set()
        for l in after_vis_links:
            href = l.get("href")
            text = (l.get("text") or "").strip()
            key = (href, text.lower())
            if key not in before_vis_links and key not in seen_revealed:
                seen_revealed.add(key)
                revealed_links.append({"href": href, "text": text})

        # 2. Detect element visibility and style changes
        before_elems = before_state.get("visibleElements", {})
        after_elems = after_state.get("visibleElements", {})

        changed_elements: dict[str, dict[str, Any]] = {}
        for key, after_prop in after_elems.items():
            before_prop = before_elems.get(key)
            if not before_prop:
                if after_prop.get("visible"):
                    changed_elements[key] = {
                        "before": {"visible": False, "opacity": 0},
                        "after": after_prop,
                        "type": "revealed",
                    }
                continue

            # Filter transient ticking clock elements from false-positive state changes
            b_text = before_prop.get("text", "")
            a_text = after_prop.get("text", "")
            if b_text != a_text and re.search(r"\b\d{2}:\d{2}:\d{2}\b", b_text + a_text):
                continue

            # Compare visibility, opacity, transform, ariaExpanded
            b_vis = before_prop.get("visible", False)
            a_vis = after_prop.get("visible", False)
            b_op = before_prop.get("opacity", 1.0)
            a_op = after_prop.get("opacity", 1.0)
            b_tf = before_prop.get("transform", "")
            a_tf = after_prop.get("transform", "")
            b_exp = before_prop.get("ariaExpanded")
            a_exp = after_prop.get("ariaExpanded")

            if (b_vis != a_vis) or (abs(b_op - a_op) > 0.1) or (b_tf != a_tf and "matrix" in (b_tf + a_tf)) or (b_exp != a_exp):
                changed_elements[key] = {
                    "before": before_prop,
                    "after": after_prop,
                    "type": "style_or_visibility_change",
                }

        has_change = bool(revealed_links or changed_elements)

        return {
            "has_change": has_change,
            "revealed_links": revealed_links,
            "changed_elements": changed_elements,
            "trigger_selector": trigger_selector,
        }

    def extract_interaction(
        self,
        interaction_id: str,
        trigger_type: str,
        candidate: dict[str, Any],
        before_state: dict[str, Any],
        after_state: dict[str, Any],
        state_diff: dict[str, Any],
        is_toggle: bool = True,
        continuous_motion: dict[str, Any] | None = None,
    ) -> InteractionIR:
        """
        Translates raw before/after diff evidence into a normalized InteractionIR.
        Infers category (menu, accordion, modal, tabs, dropdown, generic) from evidence.
        """
        revealed_links = state_diff.get("revealed_links", [])
        changed_elements = state_diff.get("changed_elements", {})
        selector = candidate.get("selector", "")
        cand_classes = candidate.get("classes", [])
        cand_text = candidate.get("text", "")

        cand_id = candidate.get("id") or ""
        # Target selection: prefer container of revealed links or changed element that is NOT the trigger itself
        target_selector = None
        target_key = None
        if changed_elements:
            other_changed = {
                k: v for k, v in changed_elements.items()
                if k != cand_id and k != selector.lstrip("#.") and "trigger" not in k.lower()
            }
            pool = other_changed if other_changed else changed_elements

            # If any elements became visible/opened in after_state, prioritize them as the primary target
            revealed_or_opened = {
                k: v for k, v in pool.items()
                if v.get("after", {}).get("visible", False) or v.get("type") == "revealed"
            }
            target_candidates = revealed_or_opened if revealed_or_opened else pool

            # Pick the most prominent changed element (e.g. nav, overlay, modal, panel, drawer, dropdown, menu)
            for k, val in target_candidates.items():
                if any(m in k.lower() for m in ("nav", "overlay", "modal", "panel", "drawer", "dropdown", "menu", "content")):
                    target_key = k
                    break
            if not target_key:
                target_key = next(iter(target_candidates.keys()))

            target_data = target_candidates.get(target_key, {})
            stored_sel = target_data.get("after", {}).get("selector") or target_data.get("before", {}).get("selector")
            if stored_sel:
                target_selector = stored_sel
            elif target_key.startswith(("#", ".", "[")):
                target_selector = target_key
            elif re.match(r"^[a-zA-Z_][a-zA-Z0-9_\-]*$", target_key):
                target_selector = f"#{target_key}"
            else:
                clean_target = target_key.replace('"', '\\"')
                target_selector = f'[data-framer-name="{clean_target}"]'

        # Category Inference based on pure evidence
        category = "generic"
        if revealed_links and len(revealed_links) >= 2:
            category = "menu"
        elif any("modal" in str(k).lower() for k in changed_elements.keys()):
            category = "modal"
        elif any("accordion" in str(k).lower() for k in changed_elements.keys()) or candidate.get("ariaExpanded") is not None:
            category = "accordion"
        elif any("tab" in str(k).lower() for k in changed_elements.keys()):
            category = "tabs"
        elif trigger_type == "hover":
            category = "hover"

        is_closing = (
            not is_toggle
            and any(w in cand_text.lower() for w in ("close", "dismiss", "hide", "cancel", "x"))
            or (changed_elements and all(
                ch.get("before", {}).get("visible", False) and not ch.get("after", {}).get("visible", False)
                for ch in changed_elements.values()
            ))
        )
        if is_toggle or category == "menu":
            action_type = "toggle"
        elif is_closing:
            action_type = "close"
        elif category == "tabs":
            action_type = "tab_select"
        elif trigger_type == "click":
            action_type = "open"
        else:
            action_type = "state_change"

        # States reconstruction: closed vs open
        closed_state: dict[str, Any] = {"target_visibility": "hidden", "opacity": 0}
        open_state: dict[str, Any] = {"target_visibility": "visible", "opacity": 1}

        if target_key and target_key in changed_elements:
            ch_data = changed_elements[target_key]
            b_data = ch_data.get("before", {})
            a_data = ch_data.get("after", {})
            closed_state.update({
                "display": b_data.get("display", "none"),
                "visibility": b_data.get("visibility", "hidden"),
                "opacity": b_data.get("opacity", 0),
                "transform": b_data.get("transform", "none"),
            })
            open_state.update({
                "display": a_data.get("display", "block"),
                "visibility": a_data.get("visibility", "visible"),
                "opacity": a_data.get("opacity", 1),
                "transform": a_data.get("transform", "none"),
            })

        animation_details: dict[str, Any] = {}
        if continuous_motion:
            animation_details["continuous"] = continuous_motion

        return InteractionIR(
            id=interaction_id,
            category=category,
            trigger=TriggerSpec(
                type=trigger_type,
                selector=selector,
                target_id=candidate.get("id"),
            ),
            action=ActionSpec(
                type=action_type,
                target=target_selector or selector,
                transition={"duration": 0.3, "easing": "ease-in-out"},
            ),
            states={
                "closed": closed_state,
                "open": open_state,
            },
            animation=animation_details,
            evidence={
                "revealed_links": revealed_links,
                "changed_count": len(changed_elements),
                "candidate_text": cand_text,
                "is_toggle": is_toggle,
            },
            description=f"Behavioral {category} interaction triggered by {trigger_type} on {selector}",
        )

    async def _safe_click(self, page: Any, selector: str) -> bool:
        """Attempts to click the element safely using Playwright."""
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.click(timeout=2000)
                return True
        except Exception:
            # Fallback to dispatching a click via evaluation
            try:
                clicked = await page.evaluate(
                    """(sel) => {
                        const el = document.querySelector(sel);
                        if (el) {
                            el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                            return true;
                        }
                        return false;
                    }""",
                    selector,
                )
                return bool(clicked)
            except Exception:
                return False
        return False

    async def _probe_hover(self, page: Any, selector: str) -> dict[str, Any] | None:
        """Probes hover state changes."""
        try:
            before = await self.snapshot_state(page)
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.hover(timeout=1500)
                await self.wait_for_settle(page)
                after = await self.snapshot_state(page)
                # Unhover
                await page.mouse.move(0, 0)
                diff = self.compare_states(before, after, trigger_selector=selector)
                diff["before"] = before
                diff["after"] = after
                return diff
        except Exception:
            pass
        return None

    async def _detect_continuous_motion(self, page: Any, selector: str) -> dict[str, Any] | None:
        """
        Detects whether an element undergoes continuous visual animation
        (e.g., CSS keyframe rotation or requestAnimationFrame updates) without user interaction.
        """
        try:
            script = """
            (sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                const style = window.getComputedStyle(el);
                const animName = style.animationName;
                const animDur = style.animationDuration;
                const animIter = style.animationIterationCount;

                if (animName && animName !== 'none' && (animIter === 'infinite' || parseFloat(animIter) > 5)) {
                    return {
                        type: 'css_animation',
                        name: animName,
                        duration: animDur,
                        iterationCount: animIter,
                    };
                }

                // Check direct children (e.g. rotating dots inside trigger wrapper)
                for (const child of el.children) {
                    const chStyle = window.getComputedStyle(child);
                    if (chStyle.animationName && chStyle.animationName !== 'none' && chStyle.animationIterationCount === 'infinite') {
                        return {
                            type: 'child_css_animation',
                            name: chStyle.animationName,
                            duration: chStyle.animationDuration,
                            iterationCount: 'infinite',
                        };
                    }
                }
                return null;
            }
            """
            res = await page.evaluate(script, selector)
            if res:
                return res
        except Exception:
            pass
        return None
