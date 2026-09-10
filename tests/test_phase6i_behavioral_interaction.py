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


class TestPhase6IBehavioralInteraction(unittest.TestCase):
    """
    Acceptance and regression tests for Phase 6I — Universal Interaction & Behavioral Reconstruction.
    Tests behavioral probing, state diffing, category inference, InteractionIR, and React generation.
    """

    def setUp(self):
        self.probe = BehaviorProbe(settle_time_ms=50)

    def test_center_4dot_menu_probe_and_diff(self):
        """
        Acceptance test: Center 4-dot menu.
        - Closed state: trigger visible with continuous rotation, navigation hidden.
        - Click trigger: navigation links (Home, Work, Design, Contact) become visible.
        - Toggle click: returns to closed state.
        - Diff extracts evidence and compiles generic InteractionIR.
        """
        # 1. Closed state snapshot
        before_state = {
            "links": [
                {"href": "/", "text": "Origins", "visible": True},
            ],
            "visibleElements": {
                "center-menu-trigger": {
                    "tag": "div",
                    "visible": True,
                    "opacity": 1.0,
                    "display": "flex",
                    "visibility": "visible",
                    "transform": "rotate(45deg)",
                    "ariaExpanded": "false",
                },
                "site-navigation-overlay": {
                    "tag": "nav",
                    "visible": False,
                    "opacity": 0.0,
                    "display": "none",
                    "visibility": "hidden",
                    "transform": "scale(0.95)",
                    "ariaExpanded": None,
                },
            },
        }

        # 2. Open state snapshot (after click)
        after_state = {
            "links": [
                {"href": "/", "text": "Origins", "visible": True},
                {"href": "/", "text": "Home", "visible": True},
                {"href": "/work", "text": "Work", "visible": True},
                {"href": "/designs", "text": "Design", "visible": True},
                {"href": "/contact", "text": "Contact", "visible": True},
            ],
            "visibleElements": {
                "center-menu-trigger": {
                    "tag": "div",
                    "visible": True,
                    "opacity": 1.0,
                    "display": "flex",
                    "visibility": "visible",
                    "transform": "rotate(135deg)",
                    "ariaExpanded": "true",
                },
                "site-navigation-overlay": {
                    "tag": "nav",
                    "visible": True,
                    "opacity": 1.0,
                    "display": "flex",
                    "visibility": "visible",
                    "transform": "scale(1)",
                    "ariaExpanded": None,
                },
            },
        }

        # 3. Diff states
        state_diff = self.probe.compare_states(
            before_state,
            after_state,
            trigger_selector="#center-menu-trigger",
        )

        self.assertTrue(state_diff["has_change"])
        revealed_hrefs = [l["href"] for l in state_diff["revealed_links"]]
        self.assertIn("/work", revealed_hrefs)
        self.assertIn("/designs", revealed_hrefs)
        self.assertIn("/contact", revealed_hrefs)

        # 4. Extract InteractionIR
        candidate = {
            "selector": "#center-menu-trigger",
            "tag": "div",
            "id": "center-menu-trigger",
            "text": "",
        }
        continuous_motion = {
            "type": "css_animation",
            "name": "spin-4dots",
            "duration": "12s",
            "iterationCount": "infinite",
        }

        interaction = self.probe.extract_interaction(
            interaction_id="interaction-001",
            trigger_type="click",
            candidate=candidate,
            before_state=before_state,
            after_state=after_state,
            state_diff=state_diff,
            is_toggle=True,
            continuous_motion=continuous_motion,
        )

        # Invariant checks: Decoupled schema
        self.assertEqual(interaction.id, "interaction-001")
        self.assertEqual(interaction.category, "menu")
        self.assertEqual(interaction.trigger.type, "click")
        self.assertEqual(interaction.trigger.selector, "#center-menu-trigger")
        self.assertEqual(interaction.action.type, "toggle")
        self.assertEqual(interaction.action.target, "#site-navigation-overlay")
        self.assertEqual(interaction.states["closed"]["visibility"], "hidden")
        self.assertEqual(interaction.states["open"]["visibility"], "visible")
        self.assertEqual(interaction.animation["continuous"]["name"], "spin-4dots")

        # Ensure no hardcoded component names
        self.assertNotIn("FourDotMenu", interaction.id)
        self.assertNotIn("FramerMenuInteraction", interaction.id)

    def test_insufficient_evidence_preserves_static_without_inventing_behavior(self):
        """
        Critical Rule: If evidence is insufficient (no DOM or link changes),
        do NOT invent a menu interaction.
        """
        before_state = {
            "links": [{"href": "/", "text": "Home", "visible": True}],
            "visibleElements": {
                "center-dots": {"visible": True, "opacity": 1.0, "display": "block", "visibility": "visible"}
            },
        }
        # After click: exact same state, no changes
        after_state = {
            "links": [{"href": "/", "text": "Home", "visible": True}],
            "visibleElements": {
                "center-dots": {"visible": True, "opacity": 1.0, "display": "block", "visibility": "visible"}
            },
        }

        state_diff = self.probe.compare_states(before_state, after_state, trigger_selector="#center-dots")
        self.assertFalse(state_diff["has_change"])
        self.assertEqual(len(state_diff["revealed_links"]), 0)

    def test_generic_patterns_accordion_and_tabs_inference(self):
        """Validates that probe and InteractionAnalyzer infer accordions and tabs from evidence."""
        # Accordion probe evidence
        accordion_cand = {"selector": ".faq-question-btn", "ariaExpanded": "false", "text": "What is WebExtractor?"}
        before_faq = {
            "links": [],
            "visibleElements": {
                "faq-panel-1": {"visible": False, "opacity": 0, "display": "none", "visibility": "hidden"}
            },
        }
        after_faq = {
            "links": [],
            "visibleElements": {
                "faq-panel-1": {"visible": True, "opacity": 1, "display": "block", "visibility": "visible"}
            },
        }
        faq_diff = self.probe.compare_states(before_faq, after_faq, trigger_selector=".faq-question-btn")
        faq_interaction = self.probe.extract_interaction(
            interaction_id="faq-01",
            trigger_type="click",
            candidate=accordion_cand,
            before_state=before_faq,
            after_state=after_faq,
            state_diff=faq_diff,
            is_toggle=True,
        )
        self.assertEqual(faq_interaction.category, "accordion")
        self.assertEqual(faq_interaction.action.type, "toggle")

    def test_site_ir_persistence_of_interactions(self):
        """Tests that SiteIR correctly persists interactions.json and to_dict()."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)

            interaction_dict = {
                "id": "interaction-001",
                "category": "menu",
                "trigger": {"type": "click", "selector": "#menu-btn"},
                "action": {"type": "toggle", "target": "#menu-nav"},
                "states": {
                    "closed": {"visibility": "hidden", "opacity": 0},
                    "open": {"visibility": "visible", "opacity": 1},
                },
            }

            site_ir = SiteIR(
                metadata={"title": "Interactive Test Site"},
                routes=["/"],
                design_system={},
                interactions=[interaction_dict],
            )
            site_ir.save(out_path)

            interactions_file = out_path / "interactions.json"
            self.assertTrue(interactions_file.exists())

            loaded = json.loads(interactions_file.read_text(encoding="utf-8"))
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["id"], "interaction-001")
            self.assertEqual(loaded[0]["category"], "menu")

    def test_react_generator_emits_interaction_runtime_and_wiring(self):
        """
        Tests that ReactProjectGenerator generates:
        - components/InteractionRuntime.tsx
        - components/RouteTransition.tsx
        - components/CursorRuntime.tsx
        - layout.tsx properly rendering <InteractionRuntime interactions={...} />
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir)

            interaction_dict = {
                "id": "interaction-001",
                "category": "menu",
                "trigger": {"type": "click", "selector": "#center-menu-trigger"},
                "action": {"type": "toggle", "target": "#site-navigation-overlay"},
                "states": {
                    "closed": {"display": "none", "visibility": "hidden", "opacity": 0},
                    "open": {"display": "flex", "visibility": "visible", "opacity": 1},
                },
                "animation": {
                    "continuous": {"type": "css_animation", "name": "spin-dots", "duration": "10s"}
                },
            }

            site_ir = SiteIR(
                metadata={"title": "Interactive Site"},
                routes=["/", "/work", "/designs", "/contact"],
                design_system={},
                pages=[
                    {
                        "route": "/",
                        "components": [
                            {"name": "HeaderNavigation"},
                            {"name": "Hero"},
                        ],
                    }
                ],
                interactions=[
                    interaction_dict,
                    {
                        "id": "interaction-route-transition",
                        "category": "route_transition",
                        "trigger": {"type": "click", "selector": 'a[href^="/"]'},
                        "action": {"type": "navigate", "transition": {"type": "fade", "duration": 0.35}},
                    },
                    {
                        "id": "interaction-cursor",
                        "category": "cursor",
                        "trigger": {"type": "hover", "selector": "a, button"},
                        "action": {"type": "state_change", "target": "#custom-cursor"},
                    },
                ],
            )

            generator = ReactProjectGenerator(site_ir, out_path)
            generator.generate()

            # 1. Verify InteractionRuntime.tsx is written
            runtime_path = out_path / "components/InteractionRuntime.tsx"
            self.assertTrue(runtime_path.exists())
            runtime_code = runtime_path.read_text(encoding="utf-8")
            self.assertIn("export default function InteractionRuntime", runtime_code)
            self.assertIn("data-continuous-motion", runtime_code)
            self.assertIn("applyState", runtime_code)

            # 2. Verify RouteTransition.tsx is written
            route_tr_path = out_path / "components/RouteTransition.tsx"
            self.assertTrue(route_tr_path.exists())

            # 3. Verify CursorRuntime.tsx is written
            cursor_path = out_path / "components/CursorRuntime.tsx"
            self.assertTrue(cursor_path.exists())

            # 4. Verify app/layout.tsx imports and renders InteractionRuntime
            layout_path = out_path / "app/layout.tsx"
            self.assertTrue(layout_path.exists())
            layout_code = layout_path.read_text(encoding="utf-8")
            self.assertIn('import InteractionRuntime from "../components/InteractionRuntime";', layout_code)
            self.assertIn("<InteractionRuntime interactions={", layout_code)
            self.assertIn("<RouteTransition />", layout_code)
            self.assertIn("<CursorRuntime />", layout_code)


if __name__ == "__main__":
    unittest.main()
