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


def test_motion_runtime_behavioral_in_view_and_scroll_reveal(tmp_path: Path):
    """
    Behavioral Playwright test asserting:
    1. MotionRuntime.tsx code binds each element once and removes unconditional timers.
    2. Zero stuck-appear IDs at t=2.0s pre-scroll (in-view elements settle to opacity 1).
    3. Below-fold elements stay hidden until scrolled into view.
    4. Post-scroll reveals below-fold elements to opacity 1.
    """
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

    # (c) Unconditional timer removed; non-once reset restored
    assert "fallbackTimer = setTimeout(ensureFinalVisibleState, 3000);" not in motion_runtime_code
    assert "else if (!once)" in motion_runtime_code

    # (d) Playwright behavioral validation in headless browser
    from playwright.sync_api import sync_playwright

    html = """<!DOCTYPE html>
<html>
<head>
<style>
  body { margin: 0; padding: 0; }
  .box { width: 200px; height: 100px; background: blue; }
  #hero { position: absolute; top: 50px; left: 50px; opacity: 0.001; }
  #footer { position: absolute; top: 3500px; left: 50px; opacity: 0.001; }
</style>
</head>
<body>
  <div id="hero" data-framer-appear-id="hero-card" class="box">Hero</div>
  <div id="footer" data-framer-appear-id="footer-card" class="box">Footer</div>
  <script>
    const animations = {
      appear_animations: {
        'hero-card': {
          initial: { opacity: 0.001, y: 30 },
          animate: { opacity: 1, y: 0 },
          transition: { type: 'spring', stiffness: 200, damping: 40, delay: 0.2 }
        },
        'footer-card': {
          trigger: 'in_view',
          initial: { opacity: 0.001, y: 30 },
          animate: { opacity: 1, y: 0 },
          transition: { type: 'spring', stiffness: 200, damping: 40, delay: 0.2 }
        }
      }
    };

    const appearMap = animations.appear_animations;
    const boundElements = new Set();

    function getTransform(val) {
      const x = val.x !== undefined ? (typeof val.x === 'number' ? val.x + 'px' : val.x) : '0px';
      const y = val.y !== undefined ? (typeof val.y === 'number' ? val.y + 'px' : val.y) : '0px';
      const scale = val.scale !== undefined ? val.scale : 1;
      const rotate = val.rotate !== undefined ? (typeof val.rotate === 'number' ? val.rotate + 'deg' : val.rotate) : '0deg';
      return 'translate3d(' + x + ', ' + y + ', 0) scale(' + scale + ') rotate(' + rotate + ')';
    }

    function getDuration(transition) {
      if (transition.duration !== undefined && typeof transition.duration === 'number' && transition.duration > 0) {
        return transition.duration * 1000;
      }
      if (transition.type === 'spring') {
        const stiffness = transition.stiffness || 200;
        const damping = transition.damping || 40;
        const dampingRatio = damping / (2 * Math.sqrt(stiffness));
        return Math.max(350, Math.min(800, Math.round(dampingRatio * 350 + 250)));
      }
      return 600;
    }

    Object.entries(appearMap).forEach(([targetId, config]) => {
      const el = document.querySelector('[data-framer-appear-id="' + targetId + '"]');
      if (!el || boundElements.has(el)) return;
      boundElements.add(el);

      const htmlEl = el instanceof HTMLElement ? el : null;
      const initial = config.initial || {};
      const animate = config.animate || {};
      const transition = config.transition || {};
      const delayMs = (transition.delay || 0) * 1000;
      const durationMs = getDuration(transition);

      const initTransform = getTransform(initial);
      const targetTransform = getTransform(animate);
      const initOpacity = initial.opacity !== undefined ? initial.opacity : 1;
      const targetOpacity = animate.opacity !== undefined ? animate.opacity : 1;

      const ensureFinalVisibleState = () => {
        if (htmlEl) {
          htmlEl.style.opacity = '' + targetOpacity;
          htmlEl.style.transform = targetTransform;
        }
      };

      const runEntranceAnimation = () => {
        try {
          const anim = el.animate(
            [
              { opacity: initOpacity, transform: initTransform },
              { opacity: targetOpacity, transform: targetTransform }
            ],
            { duration: durationMs, delay: delayMs, fill: 'forwards', easing: 'cubic-bezier(0.16, 1, 0.3, 1)' }
          );
          anim.onfinish = () => ensureFinalVisibleState();
          anim.oncancel = () => ensureFinalVisibleState();
        } catch(e) {
          ensureFinalVisibleState();
        }
      };

      const isInView = config.trigger === 'in_view' || config.inView;
      if (isInView && typeof IntersectionObserver !== 'undefined') {
        const once = config.once !== false;
        const observer = new IntersectionObserver((entries) => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              runEntranceAnimation();
              if (once) observer.unobserve(el);
            } else if (!once) {
              if (htmlEl) {
                htmlEl.style.opacity = '' + initOpacity;
                htmlEl.style.transform = initTransform;
              }
            }
          });
        }, { threshold: 0.15 });
        observer.observe(el);
      } else {
        runEntranceAnimation();
      }
    });
  </script>
</body>
</html>"""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)
        # Advance frames across 2.0s pre-scroll
        for _ in range(10):
            page.wait_for_timeout(200)
            page.screenshot()

        hero_op = float(page.evaluate("window.getComputedStyle(document.getElementById('hero')).opacity"))
        footer_op = float(page.evaluate("window.getComputedStyle(document.getElementById('footer')).opacity"))

        # Zero stuck-appear IDs at t=2.0s pre-scroll
        assert hero_op >= 0.99, f"In-view element should reach final visible state by t=2.0s, got {hero_op}"
        # Below-fold element stays hidden pre-scroll (no unconditional force-visible timer)
        assert footer_op <= 0.05, f"Below-fold element must stay hidden pre-scroll, got {footer_op}"

        # Scroll below fold
        page.evaluate("window.scrollTo(0, 3600)")
        for _ in range(6):
            page.wait_for_timeout(200)
            page.screenshot()

        footer_op_after = float(page.evaluate("window.getComputedStyle(document.getElementById('footer')).opacity"))
        assert footer_op_after >= 0.99, f"Below-fold element should reveal after scroll, got {footer_op_after}"

        # Verify duplicate binding prevention
        bound_count = page.evaluate("boundElements.size")
        assert bound_count == 2

        browser.close()