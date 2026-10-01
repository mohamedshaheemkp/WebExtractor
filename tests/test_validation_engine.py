import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from webextractor.verification.report import VerificationReport
from webextractor.verification.screenshots import ScreenshotComparator
from webextractor.verification.visual_diff import (
    ComponentDiffReportGenerator,
    VisualDiffScorer,
    generate_component_diff_report,
)


def create_mock_png(width: int, height: int, color_rgb: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Generates a valid 8-bit uncompressed PNG image bytes in memory."""
    signature = b"\x89PNG\r\n\x1a\n"

    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    ihdr_chunk = struct.pack(">I4s", len(ihdr_data), b"IHDR") + ihdr_data + struct.pack(">I", ihdr_crc)

    # IDAT (filter 0 + scanlines)
    raw_scanlines = bytearray()
    row_bytes = bytes([color_rgb[0], color_rgb[1], color_rgb[2]] * width)
    for _ in range(height):
        raw_scanlines.append(0)  # Filter type None
        raw_scanlines.extend(row_bytes)

    compressed_idat = zlib.compress(bytes(raw_scanlines))
    idat_crc = zlib.crc32(b"IDAT" + compressed_idat)
    idat_chunk = struct.pack(">I4s", len(compressed_idat), b"IDAT") + compressed_idat + struct.pack(">I", idat_crc)

    # IEND
    iend_crc = zlib.crc32(b"IEND")
    iend_chunk = struct.pack(">I4s", 0, b"IEND") + struct.pack(">I", iend_crc)

    return signature + ihdr_chunk + idat_chunk + iend_chunk


class TestValidationEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_png_header_and_pixel_decoding(self):
        """Validates that pure-Python PNG reader decodes dimensions and scanlines correctly."""
        png_data = create_mock_png(10, 10, (100, 150, 200))
        img_path = self.path / "test.png"
        img_path.write_bytes(png_data)

        header = ScreenshotComparator.read_png_header(img_path)
        self.assertIsNotNone(header)
        self.assertEqual(header["width"], 10)
        self.assertEqual(header["height"], 10)
        self.assertEqual(header["bit_depth"], 8)
        self.assertEqual(header["color_type"], 2)

        decoded = ScreenshotComparator.decode_png_pixels(img_path)
        self.assertIsNotNone(decoded)
        w, h, pixels = decoded
        self.assertEqual(w, 10)
        self.assertEqual(h, 10)
        self.assertEqual(len(pixels), 10 * 10 * 3)
        self.assertEqual(pixels[0], 100)
        self.assertEqual(pixels[1], 150)
        self.assertEqual(pixels[2], 200)

    def test_identical_screenshot_comparison(self):
        """Validates that comparing identical screenshots produces 100% similarity and PASS status."""
        img1 = self.path / "img1.png"
        img2 = self.path / "img2.png"
        png_bytes = create_mock_png(20, 20, (50, 100, 150))
        img1.write_bytes(png_bytes)
        img2.write_bytes(png_bytes)

        result = ScreenshotComparator.compare_screenshots(img1, img2)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["similarity_score"], 100.0)
        self.assertEqual(result["dimension_match"], True)
        self.assertEqual(result["mse"], 0.0)

    def test_differing_screenshot_comparison(self):
        """Validates that comparing differing images detects changes and color deltas."""
        img1 = self.path / "img1.png"
        img2 = self.path / "img2.png"
        img1.write_bytes(create_mock_png(20, 20, (0, 0, 0)))
        img2.write_bytes(create_mock_png(20, 20, (255, 255, 255)))

        result = ScreenshotComparator.compare_screenshots(img1, img2, color_tolerance=10)
        self.assertLess(result["similarity_score"], 50.0)
        self.assertEqual(result["dimension_match"], True)
        self.assertGreater(result["mse"], 1000.0)

    def test_multi_signal_fidelity_evaluation(self):
        """Validates that VisualDiffScorer computes multi-category audit across assets, layout, and tokens."""
        out_dir = self.path / "test_project"
        out_dir.mkdir()
        (out_dir / "components").mkdir()
        (out_dir / "public").mkdir()
        (out_dir / "styles").mkdir()

        # Write sample tokens.css
        (out_dir / "styles" / "tokens.css").write_text(
            ":root { --font-display: Inter; --font-body: Inter; --color-bg: #000; --container-max-width: 1200px; }",
            encoding="utf-8",
        )
        # Write mock components
        (out_dir / "components" / "Header.tsx").write_text("export default function Header() {}", encoding="utf-8")
        (out_dir / "components" / "Hero.tsx").write_text("export default function Hero() {}", encoding="utf-8")
        (out_dir / "components" / "Footer.tsx").write_text("export default function Footer() {}", encoding="utf-8")

        mock_ir = {
            "pages": [{"components": ["Header", "Hero", "Footer"]}],
            "design_system": {"colors": {"bg": "#000"}},
            "typography": {"font_families": [{"name": "Inter"}]},
            "asset_bindings": [],
            "responsive_rules": [],
            "animations": {},
            "interactions": [],
        }

        assessment = VisualDiffScorer.evaluate_fidelity(out_dir, mock_ir)
        self.assertIn("categories", assessment)
        self.assertEqual(assessment["categories"]["layout"]["status"], "PASS")
        self.assertEqual(assessment["categories"]["layout"]["matched_components"], 3)
        self.assertEqual(assessment["categories"]["typography"]["status"], "PASS")
        # Visual is NOT_RUN when no comparison evidence is passed; overall status must NEVER become PASS without comparison evidence!
        self.assertEqual(assessment["categories"]["visual"]["status"], "NOT_RUN")
        self.assertEqual(assessment["status"], "NOT_RUN")

    def test_fidelity_evaluation_with_actual_visual_evidence(self):
        """Validates that PASS status requires real visual comparison evidence, and tests BLOCKED and FAIL."""
        out_dir = self.path / "test_project_visual"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "components").mkdir(parents=True, exist_ok=True)
        (out_dir / "public").mkdir(parents=True, exist_ok=True)
        (out_dir / "styles").mkdir(parents=True, exist_ok=True)

        (out_dir / "styles" / "tokens.css").write_text(
            ":root { --font-display: Inter; --font-body: Inter; --color-bg: #000; --container-max-width: 1200px; }",
            encoding="utf-8",
        )
        (out_dir / "components" / "Header.tsx").write_text("export default function Header() {}", encoding="utf-8")
        (out_dir / "components" / "Hero.tsx").write_text("export default function Hero() {}", encoding="utf-8")
        (out_dir / "components" / "Footer.tsx").write_text("export default function Footer() {}", encoding="utf-8")

        mock_ir = {
            "pages": [{"components": ["Header", "Hero", "Footer"]}],
            "design_system": {"colors": {"bg": "#000"}},
            "typography": {"font_families": [{"name": "Inter"}]},
            "asset_bindings": [],
            "responsive_rules": [],
            "animations": {},
            "interactions": [],
        }

        # 1. Authentic visual comparison with matching screenshots -> PASS
        orig_img = self.path / "orig_desktop.png"
        gen_img = self.path / "gen_desktop.png"
        png_bytes = create_mock_png(20, 20, (10, 20, 30))
        orig_img.write_bytes(png_bytes)
        gen_img.write_bytes(png_bytes)

        orig_cap = {"screenshots": {"desktop": str(orig_img)}}
        gen_cap = {"screenshots": {"desktop": str(gen_img)}}

        res_pass = VisualDiffScorer.evaluate_fidelity(out_dir, mock_ir, orig_cap, gen_cap)
        self.assertEqual(res_pass["categories"]["visual"]["status"], "PASS")
        self.assertEqual(res_pass["status"], "PASS")

        # 2. Blocked visual comparison -> BLOCKED
        blocked_cap = {"status": "BLOCKED", "error": "Build failed"}
        res_blocked = VisualDiffScorer.evaluate_fidelity(out_dir, mock_ir, orig_cap, blocked_cap)
        self.assertEqual(res_blocked["categories"]["visual"]["status"], "BLOCKED")
        self.assertEqual(res_blocked["status"], "BLOCKED")

        # 3. Differing screenshots failing visual diff -> FAIL
        differing_img = self.path / "gen_diff.png"
        differing_img.write_bytes(create_mock_png(20, 20, (255, 255, 255)))
        diff_cap = {"screenshots": {"desktop": str(differing_img)}}
        res_fail = VisualDiffScorer.evaluate_fidelity(out_dir, mock_ir, orig_cap, diff_cap)
        self.assertEqual(res_fail["categories"]["visual"]["status"], "FAIL")
        self.assertEqual(res_fail["status"], "FAIL")

    def test_verification_report_generation(self):
        """Validates that VerificationReport writes structured JSON with categorical breakdown."""
        report_dir = self.path / "analysis"
        report_file = VerificationReport.write_report(
            output_dir=report_dir,
            similarity_score=94.5,
            components_count=6,
            assets_count=12,
            tokens_count=8,
        )

        self.assertTrue(report_file.exists())
        data = json.loads(report_file.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["overall_fidelity"], "94.5%")
        self.assertIn("categories", data)
        self.assertIn("layout", data["categories"])
        self.assertIn("typography", data["categories"])


    def test_component_region_diffing(self):
        """Validates that ScreenshotComparator.compare_region diffs bounding boxes with threshold gating."""
        img1 = self.path / "region_img1.png"
        img2 = self.path / "region_img2.png"
        img1.write_bytes(create_mock_png(100, 100, (50, 50, 50)))
        img2.write_bytes(create_mock_png(100, 100, (50, 50, 50)))

        # 1. Matching region
        rect_hero = {"x": 0, "y": 0, "width": 100, "height": 50}
        res_pass = ScreenshotComparator.compare_region(img1, img2, rect=rect_hero, threshold=5.0)
        self.assertEqual(res_pass["status"], "PASS")
        self.assertFalse(res_pass["flagged"])
        self.assertEqual(res_pass["divergence_score"], 0.0)

        # 2. Differing region above threshold
        img3 = self.path / "region_img3.png"
        img3.write_bytes(create_mock_png(100, 100, (200, 200, 200)))
        res_fail = ScreenshotComparator.compare_region(img1, img3, rect=rect_hero, threshold=5.0)
        self.assertEqual(res_fail["status"], "FAIL")
        self.assertTrue(res_fail["flagged"])
        self.assertGreater(res_fail["divergence_score"], 5.0)

    def test_component_diff_report_generator(self):
        """Validates that ComponentDiffReportGenerator produces per-component divergence list from DOM and screenshots."""
        flat_shot = self.path / "flat_shot.png"
        react_shot = self.path / "react_shot.png"
        flat_shot.write_bytes(create_mock_png(100, 200, (30, 30, 30)))
        react_shot.write_bytes(create_mock_png(100, 200, (30, 30, 30)))

        mock_dom = {
            "tag": "main",
            "children": [
                {
                    "tag": "section",
                    "attributes": {"data-component-name": "HeroSection"},
                    "rect": {"x": 0, "y": 0, "width": 100, "height": 100},
                },
                {
                    "tag": "footer",
                    "attributes": {"id": "FooterNav"},
                    "rect": {"x": 0, "y": 100, "width": 100, "height": 100},
                },
            ],
        }

        # DOM + screenshot pair
        report = ComponentDiffReportGenerator.generate(
            flat_export=(flat_shot, mock_dom),
            react_output=react_shot,
            threshold=5.0,
            breakpoint=1440,
        )

        self.assertIsInstance(report, list)
        self.assertEqual(len(report), 2)
        self.assertEqual(report[0]["component"], "HeroSection")
        self.assertEqual(report[0]["status"], "PASS")
        self.assertFalse(report[0]["flagged"])
        self.assertEqual(report[1]["component"], "FooterNav")
        self.assertEqual(report[1]["status"], "PASS")
        self.assertFalse(report.has_divergence)

        # Scorer method delegation
        scorer_report = VisualDiffScorer.generate_component_diff_report(
            flat_export=(flat_shot, mock_dom),
            react_output=react_shot,
            threshold=5.0,
        )
        self.assertEqual(len(scorer_report), 2)

    def test_continuous_animation_phase_difference_detection(self):
        """
        Validates that continuous motion phase offsets (e.g. marquee displaced horizontally by 10px)
        are detected as phase difference and pass without masking the raw divergence score.
        """
        w, h = 200, 50
        # Buffer 1: background black, white bar at x in [40..70]
        buf1_pixels = []
        for y in range(h):
            for x in range(w):
                if 40 <= x < 70:
                    buf1_pixels.extend([255, 255, 255])
                else:
                    buf1_pixels.extend([0, 0, 0])

        # Buffer 2: same bar, phase-shifted by 10px to x in [50..80]
        buf2_pixels = []
        for y in range(h):
            for x in range(w):
                if 50 <= x < 80:
                    buf2_pixels.extend([255, 255, 255])
                else:
                    buf2_pixels.extend([0, 0, 0])

        rect = {"x": 0, "y": 0, "width": w, "height": h}

        # Without phase detection: unaligned divergence should exceed threshold (10px * 50 = 500 diff pixels out of 10000 = 10%)
        unaligned = ScreenshotComparator.compare_region(
            (w, h, buf1_pixels),
            (w, h, buf2_pixels),
            rect=rect,
            threshold=5.0,
            detect_phase_shift=False,
        )
        self.assertTrue(unaligned["flagged"])
        self.assertEqual(unaligned["status"], "FAIL")
        self.assertGreater(unaligned["divergence_score"], 5.0)

        # With phase detection: detects offset of +10px, aligns, and passes
        aligned = ScreenshotComparator.compare_region(
            (w, h, buf1_pixels),
            (w, h, buf2_pixels),
            rect=rect,
            threshold=5.0,
            detect_phase_shift=True,
            max_phase_shift_px=20,
        )
        self.assertTrue(aligned.get("phase_difference_detected"))
        self.assertEqual(aligned.get("phase_offset_px"), -10)
        self.assertLessEqual(aligned.get("phase_aligned_divergence", 100), 5.0)
        self.assertEqual(aligned["status"], "PASS")
        self.assertFalse(aligned["flagged"])
        # Crucial: raw divergence is preserved for reporting
        self.assertGreater(aligned["divergence_score"], 5.0)

    def test_reconstruction_failure_not_masked_by_phase_shift(self):
        """
        Validates that genuine reconstruction failure (completely different content or broken assets)
        is NOT masked as a phase difference and correctly fails.
        """
        w, h = 200, 50
        buf1_pixels = [255, 0, 0] * (w * h)  # All red
        buf2_pixels = [0, 255, 0] * (w * h)  # All green

        rect = {"x": 0, "y": 0, "width": w, "height": h}

        res = ScreenshotComparator.compare_region(
            (w, h, buf1_pixels),
            (w, h, buf2_pixels),
            rect=rect,
            threshold=5.0,
            detect_phase_shift=True,
            max_phase_shift_px=20,
        )
        self.assertTrue(res["flagged"])
        self.assertEqual(res["status"], "FAIL")
        self.assertFalse(res.get("phase_difference_detected", False))


if __name__ == "__main__":
    unittest.main()

