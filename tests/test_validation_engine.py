import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from webextractor.verification.report import VerificationReport
from webextractor.verification.screenshots import ScreenshotComparator
from webextractor.verification.visual_diff import VisualDiffScorer


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
        self.assertEqual(assessment["status"], "PASS")

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


if __name__ == "__main__":
    unittest.main()
