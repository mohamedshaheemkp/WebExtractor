from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any

from webextractor.analysis.animations import AnimationExtractor
from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.analysis.motion_adapters.framer import FramerMotionAdapter
from webextractor.analysis.motion_adapters.standard import StandardCssMotionAdapter
from webextractor.generator.project import ReactProjectGenerator


def test_standard_adapter_cannot_handle_empty_evidence():
    """Verify standard adapter does NOT unconditionally claim capability."""
    adapter = StandardCssMotionAdapter()
    assert not adapter.can_handle(html="", css="")
    assert not adapter.can_handle(html="<div>Hello World</div>", css="body { color: red; }")
    # Only claims when actual motion signatures exist
    assert adapter.can_handle(html='<div data-aos="fade-up"></div>', css="")
    assert adapter.can_handle(html="", css=".box { transition: opacity 0.3s; }")
    assert adapter.can_handle(html="", css="@keyframes fade { from { opacity: 0; } }")


def test_adapter_priority_framer_claims_first():
    """Verify Framer adapter claims targets first, standard adapter does not claim already-claimed selectors."""
    html = """
    <div data-framer-appear-id="hero-banner" class="framer-hero-banner">Banner</div>
    """
    css = """
    .framer-hero-banner {
        transition: transform 0.5s ease-out;
    }
    .unclaimed-card {
        transition: opacity 0.8s ease-in;
    }
    """
    extractor = AnimationExtractor()
    result = extractor.analyze_motion(html_content=html, css_content=css)

    # 1. Framer adapter claimed hero-banner
    assert "hero-banner" in result["appear_animations"]
    
    # 2. Standard adapter only claimed .unclaimed-card, not .framer-hero-banner
    assert ".unclaimed-card" in result["element_transitions"]
    assert ".framer-hero-banner" not in result["element_transitions"]


def test_reconcile_motion_triggers_no_duplicates_per_target_and_records_adapter():
    """Verify at most one trigger per (target, property-set) and winning adapter is recorded."""
    existing = [
        {
            "trigger": "mount",
            "target": '[data-framer-appear-id="comp-123"]',
            "id": "comp-123",
            "adapter": "framer",
            "initial": {"opacity": 0, "y": 20},
            "animate": {"opacity": 1, "y": 0},
            "transition": {"duration": 0.6, "type": "spring"},
        }
    ]
    incoming = [
        {
            "trigger": "in_view",
            "target": '[data-framer-appear-id="comp-123"]',
            "id": "comp-123",
            "adapter": "standard",
            "initial": {"opacity": 0, "y": 40},
            "animate": {"opacity": 1, "y": 0},
            "transition": {"duration": 1.0, "type": "tween"},
        }
    ]

    AnimationExtractor.reconcile_motion_triggers(existing, incoming, adapter_name="standard")

    # Should NOT have duplicate triggers
    assert len(existing) == 1
    trg = existing[0]
    # The higher-priority adapter wins
    assert trg["adapter"] == "framer"
    assert trg["trigger"] == "mount"
    assert trg["transition"]["type"] == "spring"


def test_analyzer_does_not_append_appear_animations_to_motion_triggers():
    """Verify _extract_dom_transitions does not append duplicate triggers if already in appear_animations."""
    dom = {
        "tag": "div",
        "id": "test-box",
        "attributes": {
            "data-framer-appear-id": "framer-box-1",
        },
        "styles": {
            "transitionDuration": "0s",
            "transitionTimingFunction": "ease",
        },
        "children": [],
    }

    animations = {
        "appear_animations": {
            "framer-box-1": {
                "initial": {"opacity": 0.001, "y": 30},
                "animate": {"opacity": 1, "y": 0},
                "transition": {"duration": 0.8, "type": "spring"},
            }
        },
        "motion_triggers": [],
    }

    analyzer = SiteAnalyzer()
    analyzer._extract_dom_transitions(dom, animations)

    # Must NOT append a duplicate trigger since framer-box-1 is already in appear_animations
    assert len(animations["motion_triggers"]) == 0
    # Must NOT overwrite 0.8s spring duration with 0.0s browser default computed style
    assert animations["appear_animations"]["framer-box-1"]["transition"]["duration"] == 0.8


def test_motion_runtime_ensures_elements_bound_once_and_end_visible(tmp_path: Path):
    """Verify MotionRuntime.tsx code binds each element once and guarantees final visible state."""
    ir = {
        "metadata": {"title": "Test Visible State"},
        "pages": [{"name": "Home", "components": []}],
        "animations": {
            "appear_animations": {
                "card-1": {
                    "initial": {"opacity": 0.001, "y": 20},
                    "animate": {"opacity": 1, "y": 0},
                    "transition": {"duration": 0.5},
                }
            }
        },
    }

    out_dir = tmp_path / "test-next"
    generator = ReactProjectGenerator(site_ir=ir, output_dir=out_dir)
    generator._write_runtime_components()

    motion_runtime_code = (out_dir / "components" / "MotionRuntime.tsx").read_text(encoding="utf-8")

    # (a) No duplicate bindings per target: boundElements set
    assert "const boundElements = new Set<Element>();" in motion_runtime_code
    assert "if (!el || boundElements.has(el)) return;" in motion_runtime_code
    assert "boundElements.add(el);" in motion_runtime_code

    # (b) Elements end in final visible state: fill forwards, ensureFinalVisibleState
    assert 'fill: "forwards"' in motion_runtime_code
    assert "ensureFinalVisibleState" in motion_runtime_code
    assert "anim.onfinish = () => ensureFinalVisibleState();" in motion_runtime_code
    assert "anim.oncancel = () => ensureFinalVisibleState();" in motion_runtime_code

    # (c) No hidden initial state persists if animation fails / never fires: safety timeout
    assert "fallbackTimer = setTimeout(ensureFinalVisibleState, 3000);" in motion_runtime_code
    assert "el instanceof Element" in motion_runtime_code
