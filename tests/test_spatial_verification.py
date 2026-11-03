from __future__ import annotations

from pathlib import Path
import pytest

from webextractor.model.site_ir import SiteIR
from webextractor.verification.spatial_tree import SpatialTreeExtractor
from webextractor.verification.spatial_comparator import SpatialComparator, LayoutViolation
from webextractor.verification.auto_repair import LayoutAutoRepair


def test_spatial_tree_extractor_none_safe():
    import asyncio
    res = asyncio.run(SpatialTreeExtractor.capture(None))
    assert res == []


def test_spatial_comparator_detects_overlay_collision():
    baseline = [
        {
            "identifier": "header-nav",
            "tag": "nav",
            "className": "main-nav",
            "framerName": "",
            "rect": {"top": 0, "left": 0, "width": 1440, "height": 80, "right": 1440, "bottom": 80},
        },
        {
            "identifier": "footer-bar",
            "tag": "footer",
            "className": "main-footer",
            "framerName": "",
            "rect": {"top": 820, "left": 0, "width": 1440, "height": 80, "right": 1440, "bottom": 900},
        },
    ]

    # Reconstructed has header pushed down and footer pulled up
    reconstructed = [
        {
            "identifier": "header-nav",
            "tag": "nav",
            "className": "main-nav",
            "framerName": "",
            "rect": {"top": 200, "left": 0, "width": 1440, "height": 80, "right": 1440, "bottom": 280},
        },
        {
            "identifier": "footer-bar",
            "tag": "footer",
            "className": "main-footer",
            "framerName": "",
            "rect": {"top": 500, "left": 0, "width": 1440, "height": 80, "right": 1440, "bottom": 580},
        },
    ]

    comparator = SpatialComparator(baseline, reconstructed)
    violations = comparator.compare()

    collision_types = [v.violation_type for v in violations]
    assert "OVERLAY_COLLISION" in collision_types
    assert len(violations) >= 2


def test_spatial_comparator_detects_track_clamped():
    baseline = [
        {
            "identifier": "project-carousel",
            "tag": "div",
            "className": "carousel-track",
            "framerName": "CarouselTrack",
            "rect": {"top": 200, "left": 0, "width": 3600, "height": 600, "right": 3600, "bottom": 800},
        }
    ]

    # Reconstructed carousel collapsed to standard screen width
    reconstructed = [
        {
            "identifier": "project-carousel",
            "tag": "div",
            "className": "carousel-track",
            "framerName": "CarouselTrack",
            "rect": {"top": 200, "left": 0, "width": 600, "height": 600, "right": 600, "bottom": 800},
        }
    ]

    comparator = SpatialComparator(baseline, reconstructed)
    violations = comparator.compare()

    track_violations = [v for v in violations if v.violation_type == "TRACK_CLAMPED"]
    assert len(track_violations) == 1
    assert "flex-direction: row" in track_violations[0].details["recommended_style"]


def test_spatial_comparator_detects_viewport_shrinkage():
    baseline = [
        {
            "identifier": "main-content",
            "tag": "main",
            "className": "",
            "framerName": "Page",
            "rect": {"top": 0, "left": 0, "width": 1440, "height": 900, "right": 1440, "bottom": 900},
        }
    ]

    reconstructed = [
        {
            "identifier": "main-content",
            "tag": "main",
            "className": "",
            "framerName": "Page",
            "rect": {"top": 0, "left": 350, "width": 729, "height": 600, "right": 1079, "bottom": 600},
        }
    ]

    comparator = SpatialComparator(baseline, reconstructed)
    violations = comparator.compare()

    shrink_violations = [v for v in violations if v.violation_type == "VIEWPORT_SHRINK"]
    assert len(shrink_violations) == 1


def test_spatial_comparator_detects_media_autoplay_missing():
    baseline = []
    reconstructed = [
        {
            "identifier": "hero-video",
            "tag": "video",
            "className": "hero-bg",
            "framerName": "",
            "rect": {"top": 0, "left": 0, "width": 1440, "height": 900, "right": 1440, "bottom": 900},
            "videoAttributes": {
                "autoplay": False,
                "muted": True,
                "loop": True,
                "playsInline": True,
            },
        }
    ]

    comparator = SpatialComparator(baseline, reconstructed)
    violations = comparator.compare()

    media_violations = [v for v in violations if v.violation_type == "MEDIA_AUTOPLAY_MISSING"]
    assert len(media_violations) == 1


def test_auto_repair_applies_css_and_patches_ir(tmp_path: Path):
    site_ir = SiteIR(
        metadata={"url": "https://example.com"},
        routes=[],
        design_system={},
        reusable_components=[
            {"name": "HeroVideo", "tag": "video", "attributes": {}}
        ],
    )

    violations = [
        LayoutViolation(
            violation_type="OVERLAY_COLLISION",
            identifier="HeaderNav",
            target_element="header",
            details={
                "role": "header",
                "recommended_style": "position: fixed; top: 0; left: 0; width: 100%; z-index: 50;",
            },
        ),
        LayoutViolation(
            violation_type="TRACK_CLAMPED",
            identifier="carousel_track",
            target_element="div",
            details={
                "recommended_style": "display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; width: max-content !important;",
            },
        ),
        LayoutViolation(
            violation_type="VIEWPORT_SHRINK",
            identifier="main",
            target_element="main",
            details={},
        ),
        LayoutViolation(
            violation_type="MEDIA_AUTOPLAY_MISSING",
            identifier="hero-video",
            target_element="video",
            details={},
        ),
    ]

    styles_dir = tmp_path / "styles"
    styles_dir.mkdir(parents=True)
    framer_css = styles_dir / "framer.css"
    framer_css.write_text("/* Original Framer CSS */\n.framer-node { display: block; }\n", encoding="utf-8")

    modified = LayoutAutoRepair.apply_repairs(site_ir, violations, tmp_path)
    assert modified is True

    # Check layout_repairs.css was created
    repairs_css = styles_dir / "layout_repairs.css"
    assert repairs_css.exists()
    content = repairs_css.read_text(encoding="utf-8")
    assert "position: fixed;" in content
    assert "flex-direction: row" in content
    assert "width: 100% !important;" in content

    # Check framer.css was prepended with import
    framer_content = framer_css.read_text(encoding="utf-8")
    assert "@import './layout_repairs.css';" in framer_content

    # Check site_ir video attributes patched
    assert site_ir.reusable_components[0]["attributes"]["autoPlay"] is True
    assert site_ir.reusable_components[0]["attributes"]["muted"] is True
    assert site_ir.reusable_components[0]["attributes"]["loop"] is True
    assert site_ir.reusable_components[0]["attributes"]["playsInline"] is True
