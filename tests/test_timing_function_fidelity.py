import pytest
from pathlib import Path
from webextractor.analysis.motion_adapters.standard import StandardCssMotionAdapter
from webextractor.analysis.analyzer import SiteAnalyzer
from webextractor.generator.project import ReactProjectGenerator
from webextractor.generator.static import StaticProjectGenerator


def test_standard_adapter_preserves_cubic_bezier():
    """Verify source cubic-bezier survives extraction and is NOT replaced by ease."""
    css = """
    .hero-banner {
        transition: transform 1.2s cubic-bezier(0.44, 0, 0.56, 1);
    }
    """
    adapter = StandardCssMotionAdapter()
    result = adapter.extract_motion(html="", css=css)

    assert result["default_timing_function"] == "cubic-bezier(0.44, 0, 0.56, 1)"
    assert result["timing_function"] == "cubic-bezier(0.44, 0, 0.56, 1)"
    assert result["timing_function"] != "ease"

    elem_trans = result["element_transitions"].get(".hero-banner")
    assert elem_trans is not None
    assert elem_trans["duration"] == 1.2
    assert elem_trans["timing_function"] == "cubic-bezier(0.44, 0, 0.56, 1)"
    assert elem_trans["timing_function"] != "ease"
    # Backward compatibility
    assert elem_trans["easing"] == "cubic-bezier(0.44, 0, 0.56, 1)"
    assert elem_trans["ease"] == "cubic-bezier(0.44, 0, 0.56, 1)"


def test_standard_adapter_preserves_steps():
    """Verify source steps(...) timing function survives extraction."""
    css = """
    .sprite-animation {
        transition: background-position 0.8s steps(8, end);
    }
    """
    adapter = StandardCssMotionAdapter()
    result = adapter.extract_motion(html="", css=css)

    assert result["default_timing_function"] == "steps(8, end)"
    assert result["timing_function"] == "steps(8, end)"

    elem_trans = result["element_transitions"].get(".sprite-animation")
    assert elem_trans is not None
    assert elem_trans["duration"] == 0.8
    assert elem_trans["timing_function"] == "steps(8, end)"
    assert elem_trans["timing_function"] != "ease"


def test_standard_adapter_handles_leading_decimal_duration():
    """Verify durations like .3s or .15s are correctly parsed rather than truncated."""
    css = """
    .framer-card {
        transition: all .3s cubic-bezier(.44,0,.56,1) 0s;
    }
    """
    adapter = StandardCssMotionAdapter()
    result = adapter.extract_motion(html="", css=css)

    elem_trans = result["element_transitions"].get(".framer-card")
    assert elem_trans is not None
    assert elem_trans["duration"] == 0.3
    assert elem_trans["timing_function"] == "cubic-bezier(.44,0,.56,1)"


def test_dom_computed_style_transition_propagation():
    """Verify DOM computed-style transitions propagate to appear_animations and motion_triggers."""
    dom = {
        "tag": "div",
        "id": "hero-section",
        "classes": ["hero-class"],
        "attributes": {
            "data-framer-appear-id": "hero-appear-99",
            "data-motion-id": "motion-99",
        },
        "styles": {
            "transitionDuration": "1.2s",
            "transitionTimingFunction": "cubic-bezier(0.44, 0, 0.56, 1)",
            "transitionProperty": "transform, opacity",
        },
        "children": [],
    }

    analyzer = SiteAnalyzer()
    animations = {
        "appear_animations": {
            "hero-appear-99": {
                "initial": {"opacity": 0, "y": 20},
                "animate": {"opacity": 1, "y": 0},
                "transition": {"duration": 0.6, "type": "spring"},
            }
        },
        "motion_triggers": [
            {
                "trigger": "mount",
                "target": '[data-framer-appear-id="hero-appear-99"]',
                "transition": {"duration": 0.6, "type": "spring"},
            }
        ],
    }

    analyzer._extract_dom_transitions(dom, animations)

    # 1. Verify appear_animations was updated
    hero_cfg = animations["appear_animations"]["hero-appear-99"]
    assert hero_cfg["transition"]["timing_function"] == "cubic-bezier(0.44, 0, 0.56, 1)"
    assert hero_cfg["transition"]["duration"] == 1.2
    assert hero_cfg["transition"]["timing_function"] != "ease"

    # 2. Verify motion_triggers was updated
    trigger = animations["motion_triggers"][0]
    assert trigger["transition"]["timing_function"] == "cubic-bezier(0.44, 0, 0.56, 1)"
    assert trigger["transition"]["duration"] == 1.2
    assert trigger["transition"]["timing_function"] != "ease"

    # 3. Verify element_transitions has the selector
    assert "#hero-section" in animations["element_transitions"]
    elem_trans = animations["element_transitions"]["#hero-section"]
    assert elem_trans["timing_function"] == "cubic-bezier(0.44, 0, 0.56, 1)"
    assert elem_trans["duration"] == 1.2


def test_nextjs_generator_emits_cubic_bezier_into_globals_css(tmp_path: Path):
    """Verify Next.js generator outputs cubic-bezier into app/globals.css and NOT ease."""
    ir = {
        "pages": [{"name": "Home", "components": []}],
        "reusable_components": [],
        "component_styles": {},
        "tokens": {"colors": [], "fonts": []},
        "animations": {
            "timing_function": "cubic-bezier(0.44, 0, 0.56, 1)",
            "default_transition_duration": 1.2,
            "element_transitions": {
                ".hero-animated": {
                    "duration": 1.2,
                    "timing_function": "cubic-bezier(0.44, 0, 0.56, 1)",
                }
            },
        },
    }

    gen = ReactProjectGenerator(site_ir=ir, output_dir=tmp_path / "next-out")
    gen._write_global_styles()

    globals_css = (tmp_path / "next-out" / "app" / "globals.css").read_text(encoding="utf-8")
    assert "cubic-bezier(0.44, 0, 0.56, 1)" in globals_css
    assert ".hero-animated" in globals_css
    assert "transition: all 1.2s cubic-bezier(0.44, 0, 0.56, 1) !important;" in globals_css
    # Assert it was NOT replaced by ease
    assert "transition: all 1.2s ease !important;" not in globals_css


def test_static_generator_emits_steps_into_styles_css(tmp_path: Path):
    """Verify Static HTML generator outputs steps(...) into css/styles.css and NOT ease."""
    ir = {
        "metadata": {"title": "Test Site"},
        "pages": [{"route": "/", "title": "Home", "components": []}],
        "tokens": {"colors": [], "fonts": []},
        "animations": {
            "timing_function": "steps(4, end)",
            "default_transition_duration": 0.8,
            "element_transitions": {
                ".stepped-box": {
                    "duration": 0.8,
                    "timing_function": "steps(4, end)",
                }
            },
        },
    }

    gen = StaticProjectGenerator(site_ir=ir, output_dir=tmp_path / "static-out")
    gen._write_styles()

    styles_css = (tmp_path / "static-out" / "css" / "styles.css").read_text(encoding="utf-8")
    assert "steps(4, end)" in styles_css
    assert ".stepped-box" in styles_css
    assert "transition: all 0.8s steps(4, end) !important;" in styles_css
    assert "transition: all 0.8s ease !important;" not in styles_css


def test_timing_and_duration_spec_fidelity():
    """
    Verify exact parsing for:
    - .3s, 0.3s, 1.2s, 0s
    - cubic-bezier(0.44, 0, 0.56, 1)
    - steps(4, jump-end)
    - ease-in-out
    - linear
    - No confusion between duration and delay (e.g. 0s duration with 1.2s delay).
    """
    css = """
    .case-zero-duration {
        transition: opacity 0s linear 1.2s;
    }
    .case-leading-decimal {
        transition: all .3s cubic-bezier(0.44, 0, 0.56, 1) 0.5s;
    }
    .case-standard-decimal {
        transition: color 0.3s ease-in-out;
    }
    .case-steps-jump {
        transition: transform 1.2s steps(4, jump-end);
    }
    """
    adapter = StandardCssMotionAdapter()
    result = adapter.extract_motion(html="", css=css)
    et = result["element_transitions"]

    # 1. Zero duration with delay: must NOT confuse 0s duration with 1.2s delay
    zero_case = et[".case-zero-duration"]
    assert zero_case["duration"] == 0.0
    assert zero_case["delay"] == 1.2
    assert zero_case["timing_function"] == "linear"

    # 2. Leading decimal .3s: duration 0.3, delay 0.5, cubic-bezier
    leading_case = et[".case-leading-decimal"]
    assert leading_case["duration"] == 0.3
    assert leading_case["delay"] == 0.5
    assert leading_case["timing_function"] == "cubic-bezier(0.44, 0, 0.56, 1)"

    # 3. Standard decimal 0.3s: duration 0.3, ease-in-out
    std_case = et[".case-standard-decimal"]
    assert std_case["duration"] == 0.3
    assert std_case["timing_function"] == "ease-in-out"

    # 4. 1.2s duration: steps(4, jump-end)
    steps_case = et[".case-steps-jump"]
    assert steps_case["duration"] == 1.2
    assert steps_case["timing_function"] == "steps(4, jump-end)"


def test_framer_fixture_capture_to_site_ir_survival(tmp_path: Path):
    """
    Verify known source timing functions survive end-to-end:
    capture -> analyzer -> SiteIR -> site_ir.json
    """
    from webextractor.model.site_ir import SiteIR
    import json

    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Framer App</title>
        <style>
          .hero-appear {
            transition: transform 1.2s cubic-bezier(0.44, 0, 0.56, 1);
          }
        </style>
        <script type="application/json">
          {
            "framer-hero-appear": {
              "default": {
                "initial": {"opacity": 0, "y": 20},
                "animate": {
                  "opacity": 1,
                  "y": 0,
                  "transition": {
                    "duration": 1.2,
                    "ease": [0.44, 0, 0.56, 1]
                  }
                }
              }
            }
          }
        </script>
      </head>
      <body>
        <div id="hero" data-framer-appear-id="framer-hero-appear" class="hero-appear">
          Hero Content
        </div>
      </body>
    </html>
    """

    capture = {
        "url": "https://test.framer.app/",
        "html": html,
        "css": ".hero-appear { transition: transform 1.2s cubic-bezier(0.44, 0, 0.56, 1); }",
        "dom": {
            "tag": "div",
            "id": "hero",
            "classes": ["hero-appear"],
            "attributes": {
                "data-framer-appear-id": "framer-hero-appear",
            },
            "styles": {
                "transitionDuration": "1.2s",
                "transitionTimingFunction": "cubic-bezier(0.44, 0, 0.56, 1)",
            },
            "children": [],
        },
        "viewports": {},
    }

    analyzer = SiteAnalyzer()
    site_model = analyzer.analyze(capture)

    site_ir = SiteIR(
        metadata={"url": site_model.url, "title": site_model.title},
        routes=site_model.routes,
        design_system=getattr(site_model, "design_system", {}),
        animations=getattr(site_model, "animations", {}),
    )

    site_ir.save(tmp_path / "analysis")
    ir_file = tmp_path / "analysis" / "site_ir.json"
    assert ir_file.exists()

    with open(ir_file, "r", encoding="utf-8") as f:
        saved_ir = json.load(f)

    anims = saved_ir.get("animations", {})
    # 1. Root timing function must be the source curve
    assert anims.get("timing_function") == "cubic-bezier(0.44, 0, 0.56, 1)"
    # 2. appear_animations must preserve the curve
    appear_cfg = anims["appear_animations"]["framer-hero-appear"]
    assert appear_cfg["transition"]["timing_function"] == "cubic-bezier(0.44, 0, 0.56, 1)"
    assert appear_cfg["transition"]["duration"] == 1.2
    # 3. motion_triggers must be updated
    assert len(anims["motion_triggers"]) > 0
    trigger = next(t for t in anims["motion_triggers"] if "framer-hero-appear" in t.get("target", "") or t.get("id") == "framer-hero-appear")
    assert trigger["transition"]["timing_function"] == "cubic-bezier(0.44, 0, 0.56, 1)"
    assert trigger["transition"]["duration"] == 1.2

