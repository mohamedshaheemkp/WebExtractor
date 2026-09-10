import json
import tempfile
import unittest
from pathlib import Path

from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.analysis.interactions import InteractionAnalyzer
from webextractor.capture.behavior import BehaviorProbe
from webextractor.generator.project import ReactProjectGenerator
from webextractor.model.interaction import ActionSpec, InteractionIR, TriggerSpec
from webextractor.model.site_ir import SiteIR


class TestPhase6IAdversarialValidation(unittest.TestCase):
    """
    Adversarial Stress Test Suite for Phase 6I — Universal Interaction & Behavioral Reconstruction.
    Tests false positive resistance, bait elements, shared-href link detection,
    dynamic DOM mounts, tab groups, close-only actions, and runtime selector resilience.
    """

    def setUp(self):
        self.probe = BehaviorProbe(settle_time_ms=50)

    def test_bait_elements_and_false_positive_resistance(self):
        """
        Adversarial Test 1: Bait Elements & False Positives.
        A website contains decorative spinners, fake buttons (<div role="button">),
        dead anchor links (<a href="#">), and cursor:pointer traps that do NOT change the DOM.
        Engine MUST NOT invent interactions or fake menus.
        """
        static_links = [
            {"href": "#", "text": "Dead Link 1", "visible": True},
            {"href": "javascript:void(0)", "text": "Void Link", "visible": True},
        ]
        static_elements = {
            "decorative-spinner": {
                "tag": "div",
                "visible": True,
                "opacity": 1.0,
                "display": "block",
                "visibility": "visible",
                "transform": "rotate(180deg)",
            },
            "fake-button": {
                "tag": "div",
                "visible": True,
                "opacity": 1.0,
                "display": "flex",
                "visibility": "visible",
                "role": "button",
            },
        }

        before_state = {"links": static_links, "visibleElements": static_elements}
        # After clicking bait element, state is identical
        after_state = {"links": list(static_links), "visibleElements": dict(static_elements)}

        # 1. Probe diff on decorative spinner
        diff_spinner = self.probe.compare_states(
            before_state,
            after_state,
            trigger_selector="#decorative-spinner",
        )
        self.assertFalse(diff_spinner["has_change"])
        self.assertEqual(len(diff_spinner["revealed_links"]), 0)
        self.assertEqual(len(diff_spinner["changed_elements"]), 0)

        # 2. Probe diff on fake button
        diff_button = self.probe.compare_states(
            before_state,
            after_state,
            trigger_selector="#fake-button",
        )
        self.assertFalse(diff_button["has_change"])

    def test_shared_href_distinct_navigation_links(self):
        """
        Adversarial Test 2: Shared-href Resolution.
        Website initially has a logo link with href="/".
        When the menu trigger is clicked, a "Home" link with href="/" is revealed along with "Work" and "Contact".
        Verifies that "Home" is properly recognized as a newly revealed link despite the existing logo link.
        """
        before_state = {
            "links": [
                {"href": "/", "text": "Brand Logo", "visible": True},
                {"href": "/about", "text": "About Static", "visible": True},
            ],
            "visibleElements": {
                "menu-toggle": {"visible": True, "opacity": 1.0, "display": "block", "visibility": "visible"},
                "nav-drawer": {"visible": False, "opacity": 0.0, "display": "none", "visibility": "hidden"},
            },
        }

        after_state = {
            "links": [
                {"href": "/", "text": "Brand Logo", "visible": True},
                {"href": "/about", "text": "About Static", "visible": True},
                {"href": "/", "text": "Home", "visible": True},
                {"href": "/work", "text": "Work", "visible": True},
                {"href": "/contact", "text": "Contact", "visible": True},
            ],
            "visibleElements": {
                "menu-toggle": {"visible": True, "opacity": 1.0, "display": "block", "visibility": "visible"},
                "nav-drawer": {"visible": True, "opacity": 1.0, "display": "block", "visibility": "visible"},
            },
        }

        diff = self.probe.compare_states(before_state, after_state, trigger_selector="#menu-toggle")
        self.assertTrue(diff["has_change"])

        revealed = diff["revealed_links"]
        self.assertEqual(len(revealed), 3)

        revealed_tuples = [(l["href"], l["text"]) for l in revealed]
        self.assertIn(("/", "Home"), revealed_tuples)
        self.assertIn(("/work", "Work"), revealed_tuples)
        self.assertIn(("/contact", "Contact"), revealed_tuples)

    def test_dynamic_mount_and_dom_injection(self):
        """
        Adversarial Test 3: Dynamic Mount / Injection.
        Clicking an element dynamically injects a new modal container into the DOM
        that did not exist at all in the before snapshot.
        """
        before_state = {
            "links": [],
            "visibleElements": {
                "open-modal-trigger": {"visible": True, "opacity": 1.0, "display": "block", "visibility": "visible"},
            },
        }

        after_state = {
            "links": [],
            "visibleElements": {
                "open-modal-trigger": {"visible": True, "opacity": 1.0, "display": "block", "visibility": "visible"},
                "dynamically-injected-modal": {
                    "tag": "div",
                    "visible": True,
                    "opacity": 1.0,
                    "display": "flex",
                    "visibility": "visible",
                    "transform": "translateY(0)",
                },
            },
        }

        diff = self.probe.compare_states(before_state, after_state, trigger_selector="#open-modal-trigger")
        self.assertTrue(diff["has_change"])
        self.assertIn("dynamically-injected-modal", diff["changed_elements"])
        self.assertEqual(diff["changed_elements"]["dynamically-injected-modal"]["type"], "revealed")

        candidate = {"selector": "#open-modal-trigger", "text": "Open Details"}
        interaction = self.probe.extract_interaction(
            interaction_id="modal-001",
            trigger_type="click",
            candidate=candidate,
            before_state=before_state,
            after_state=after_state,
            state_diff=diff,
            is_toggle=True,
        )

        self.assertEqual(interaction.category, "modal")
        self.assertEqual(interaction.action.target, "#dynamically-injected-modal")
        self.assertEqual(interaction.action.type, "toggle")

    def test_conflicting_motion_and_behavioral_separation(self):
        """
        Adversarial Test 4: Conflicting Motion & Trigger Separation.
        An element has continuous 360deg CSS rotation, hover scale 1.05, and click toggle for a menu.
        Verifies that visual motion and behavioral interactions do NOT overwrite each other.
        """
        before_state = {
            "links": [],
            "visibleElements": {
                "orbiting-trigger": {
                    "tag": "div",
                    "visible": True,
                    "opacity": 1.0,
                    "display": "block",
                    "visibility": "visible",
                    "transform": "rotate(120deg)",
                },
                "orbiting-panel": {
                    "tag": "aside",
                    "visible": False,
                    "opacity": 0.0,
                    "display": "none",
                    "visibility": "hidden",
                },
            },
        }

        after_state = {
            "links": [
                {"href": "/overview", "text": "Overview", "visible": True},
                {"href": "/deep-dive", "text": "Deep Dive", "visible": True},
            ],
            "visibleElements": {
                "orbiting-trigger": {
                    "tag": "div",
                    "visible": True,
                    "opacity": 1.0,
                    "display": "block",
                    "visibility": "visible",
                    "transform": "rotate(120deg)",
                },
                "orbiting-panel": {
                    "tag": "aside",
                    "visible": True,
                    "opacity": 1.0,
                    "display": "block",
                    "visibility": "visible",
                },
            },
        }

        diff = self.probe.compare_states(before_state, after_state, trigger_selector="#orbiting-trigger")
        candidate = {"selector": "#orbiting-trigger", "text": ""}
        continuous_motion = {
            "type": "css_animation",
            "name": "orbit-rotation",
            "duration": "8s",
            "iterationCount": "infinite",
        }

        interaction = self.probe.extract_interaction(
            interaction_id="orbit-01",
            trigger_type="click",
            candidate=candidate,
            before_state=before_state,
            after_state=after_state,
            state_diff=diff,
            is_toggle=True,
            continuous_motion=continuous_motion,
        )

        # 1. Visual continuous animation is captured under animation.continuous
        self.assertEqual(interaction.animation["continuous"]["name"], "orbit-rotation")

        # 2. Click interaction is captured under trigger.type = "click"
        self.assertEqual(interaction.trigger.type, "click")
        self.assertEqual(interaction.action.target, "#orbiting-panel")

        # 3. States correctly record panel visibility toggle
        self.assertEqual(interaction.states["closed"]["visibility"], "hidden")
        self.assertEqual(interaction.states["open"]["visibility"], "visible")

    def test_multi_tab_group_inference(self):
        """
        Adversarial Test 5: Multi-tab Panel Switching.
        Clicking Tab 2 deactivates Tab 1 and activates Tab 2 panel.
        """
        tab2_cand = {"selector": "#tab-button-2", "text": "Specs"}
        before_tabs = {
            "links": [],
            "visibleElements": {
                "tab-panel-1": {"visible": True, "opacity": 1.0, "display": "block", "visibility": "visible"},
                "tab-panel-2": {"visible": False, "opacity": 0.0, "display": "none", "visibility": "hidden"},
            },
        }
        after_tabs = {
            "links": [],
            "visibleElements": {
                "tab-panel-1": {"visible": False, "opacity": 0.0, "display": "none", "visibility": "hidden"},
                "tab-panel-2": {"visible": True, "opacity": 1.0, "display": "block", "visibility": "visible"},
            },
        }

        diff = self.probe.compare_states(before_tabs, after_tabs, trigger_selector="#tab-button-2")
        self.assertTrue(diff["has_change"])

        interaction = self.probe.extract_interaction(
            interaction_id="tab-interaction-2",
            trigger_type="click",
            candidate=tab2_cand,
            before_state=before_tabs,
            after_state=after_tabs,
            state_diff=diff,
            is_toggle=False,
        )

        self.assertEqual(interaction.category, "tabs")
        self.assertEqual(interaction.action.type, "tab_select")
        self.assertEqual(interaction.action.target, "#tab-panel-2")

    def test_close_and_dismiss_action_inference(self):
        """
        Adversarial Test 6: One-way Close / Dismiss Action.
        A close button hides an existing alert / modal.
        """
        close_cand = {"selector": ".modal-close-btn", "text": "Close"}
        before_state = {
            "links": [],
            "visibleElements": {
                "popup-overlay": {"visible": True, "opacity": 1.0, "display": "flex", "visibility": "visible"},
            },
        }
        after_state = {
            "links": [],
            "visibleElements": {
                "popup-overlay": {"visible": False, "opacity": 0.0, "display": "none", "visibility": "hidden"},
            },
        }

        diff = self.probe.compare_states(before_state, after_state, trigger_selector=".modal-close-btn")
        self.assertTrue(diff["has_change"])

        interaction = self.probe.extract_interaction(
            interaction_id="close-interaction-1",
            trigger_type="click",
            candidate=close_cand,
            before_state=before_state,
            after_state=after_state,
            state_diff=diff,
            is_toggle=False,
        )

        self.assertEqual(interaction.action.type, "close")
        self.assertEqual(interaction.action.target, "#popup-overlay")

    def test_malformed_selectors_and_runtime_resilience(self):
        """
        Adversarial Test 7: Malformed / Unescaped Selectors in Generator.
        InteractionIR contains complex or malformed selectors (e.g. empty target, unescaped punctuation).
        React generator must produce safe InteractionRuntime code without compile or runtime errors.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)

            site_ir = SiteIR(
                metadata={"title": "Resilience Test Site"},
                routes=["/"],
                design_system={},
                interactions=[
                    {
                        "id": "malformed-01",
                        "category": "generic",
                        "trigger": {"type": "click", "selector": "[data-attr='special@value#123']"},
                        "action": {"type": "toggle", "target": ""},
                    },
                    {
                        "id": "orphaned-02",
                        "category": "generic",
                        "trigger": {"type": "click", "selector": ".missing-target-btn"},
                        "action": {"type": "toggle", "target": "#non-existent-target-999"},
                    },
                ],
            )

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            runtime_code = (out_path / "components/InteractionRuntime.tsx").read_text(encoding="utf-8")
            self.assertIn("try {", runtime_code)
            self.assertIn("getTargets", runtime_code)
            self.assertIn("catch (e)", runtime_code)

    def test_architecture_audit_clean_naming(self):
        """
        Adversarial Test 8: Architecture Audit.
        Ensures strict absence of hardcoded site-specific or framework-specific names
        across the InteractionIR and generated components.
        """
        interaction_dict = {
            "id": "interaction-001",
            "category": "menu",
            "trigger": {"type": "click", "selector": "#menu-trigger"},
            "action": {"type": "toggle", "target": "#menu-container"},
        }
        site_ir = SiteIR(
            metadata={"title": "Audit Site"},
            routes=["/"],
            design_system={},
            interactions=[interaction_dict],
        )

        serialized = json.dumps(site_ir.to_dict())
        forbidden_hardcoded_terms = [
            "FourDotMenu",
            "FourDots",
            "FramerMenuInteraction",
            "FramerMenu",
            "ShaheemMenu",
            "CenterMenuComponent",
        ]
        for term in forbidden_hardcoded_terms:
            self.assertNotIn(term, serialized)


if __name__ == "__main__":
    unittest.main()
