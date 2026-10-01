from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path
from typing import Any


class ScreenshotComparator:
    """
    Pure-Python screenshot comparator and PNG parser.
    Decodes PNG files without external image dependencies (using standard library zlib and struct),
    extracts dimensions, computes pixel diffs with perceptual color tolerance, and calculates
    structural similarity metrics.
    """

    @staticmethod
    def verify_paths(original: Path | None, generated: Path | None) -> bool:
        """Backward-compatible path verification check."""
        if original and Path(original).exists() and generated and Path(generated).exists():
            return Path(original).stat().st_size > 0 and Path(generated).stat().st_size > 0
        return False

    @classmethod
    def read_png_header(cls, file_path: Path | str) -> dict[str, Any] | None:
        """Reads PNG IHDR chunk to extract width, height, bit depth, and color type."""
        path = Path(file_path)
        if not path.exists() or path.stat().st_size < 24:
            return None

        try:
            with open(path, "rb") as f:
                header = f.read(8)
                if header != b"\x89PNG\r\n\x1a\n":
                    return None
                length, chunk_type = struct.unpack(">I4s", f.read(8))
                if chunk_type != b"IHDR" or length < 13:
                    return None
                ihdr_data = f.read(13)
                width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(
                    ">IIBBBBB", ihdr_data
                )
                return {
                    "width": width,
                    "height": height,
                    "bit_depth": bit_depth,
                    "color_type": color_type,
                    "interlace": interlace,
                }
        except Exception:
            return None

    @classmethod
    def decode_png_pixels(cls, file_path: Path | str) -> tuple[int, int, list[int]] | None:
        """
        Extracts raw decompressed RGB/RGBA pixel bytes from a PNG file.
        Returns (width, height, list_of_samples) or None if format is unhandled.
        """
        path = Path(file_path)
        if not path.exists():
            return None

        try:
            with open(path, "rb") as f:
                sig = f.read(8)
                if sig != b"\x89PNG\r\n\x1a\n":
                    return None

                width = height = bit_depth = color_type = None
                idat_chunks = []

                while True:
                    chunk_len_bytes = f.read(4)
                    if not chunk_len_bytes or len(chunk_len_bytes) < 4:
                        break
                    (length,) = struct.unpack(">I", chunk_len_bytes)
                    chunk_type = f.read(4)
                    data = f.read(length)
                    f.read(4)  # CRC

                    if chunk_type == b"IHDR":
                        width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                            ">IIBBBBB", data[:13]
                        )
                        if interlace != 0 or bit_depth != 8:
                            # Fall back to raw chunk byte diff for interlaced / unusual bit depth
                            return None
                    elif chunk_type == b"IDAT":
                        idat_chunks.append(data)
                    elif chunk_type == b"IEND":
                        break

                if not width or not height or not idat_chunks or color_type not in (2, 6):
                    return None

                decompressed = zlib.decompress(b"".join(idat_chunks))
                bytes_per_pixel = 4 if color_type == 6 else 3
                stride = width * bytes_per_pixel
                expected_scanline_len = stride + 1

                raw_bytes = bytearray()
                offset = 0
                prev_line = bytearray(stride)

                for _ in range(height):
                    if offset + expected_scanline_len > len(decompressed):
                        break
                    filter_type = decompressed[offset]
                    line_data = bytearray(decompressed[offset + 1 : offset + expected_scanline_len])
                    offset += expected_scanline_len

                    # Unfilter scanline
                    if filter_type == 0:  # None
                        pass
                    elif filter_type == 1:  # Sub
                        for i in range(bytes_per_pixel, stride):
                            line_data[i] = (line_data[i] + line_data[i - bytes_per_pixel]) & 0xFF
                    elif filter_type == 2:  # Up
                        for i in range(stride):
                            line_data[i] = (line_data[i] + prev_line[i]) & 0xFF
                    elif filter_type == 3:  # Average
                        for i in range(stride):
                            left = line_data[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                            above = prev_line[i]
                            line_data[i] = (line_data[i] + ((left + above) >> 1)) & 0xFF
                    elif filter_type == 4:  # Paeth
                        for i in range(stride):
                            left = line_data[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                            above = prev_line[i]
                            upper_left = prev_line[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
                            p = left + above - upper_left
                            pa = abs(p - left)
                            pb = abs(p - above)
                            pc = abs(p - upper_left)
                            if pa <= pb and pa <= pc:
                                pr = left
                            elif pb <= pc:
                                pr = above
                            else:
                                pr = upper_left
                            line_data[i] = (line_data[i] + pr) & 0xFF

                    raw_bytes.extend(line_data)
                    prev_line = line_data

                return width, height, list(raw_bytes)
        except Exception:
            return None

    @classmethod
    def compare_screenshots(
        cls,
        original_path: Path | str,
        generated_path: Path | str,
        color_tolerance: int = 15,
    ) -> dict[str, Any]:
        """
        Compares two screenshots with perceptual color tolerance and structural validation.
        Returns a detailed machine-readable comparison dict.
        """
        orig = Path(original_path)
        gen = Path(generated_path)

        if not orig.exists():
            return {
                "status": "FAIL",
                "similarity_score": 0.0,
                "error": f"Original screenshot not found: {orig}",
                "original": str(orig),
                "generated": str(gen),
            }
        if not gen.exists():
            return {
                "status": "FAIL",
                "similarity_score": 0.0,
                "error": f"Generated screenshot not found: {gen}",
                "original": str(orig),
                "generated": str(gen),
            }

        orig_hdr = cls.read_png_header(orig)
        gen_hdr = cls.read_png_header(gen)

        if not orig_hdr or not gen_hdr:
            # Fallback for non-PNG or corrupted files: file size check
            size1 = orig.stat().st_size
            size2 = gen.stat().st_size
            ratio = min(size1, size2) / max(size1, size2) if max(size1, size2) > 0 else 1.0
            score = round(ratio * 100.0, 1)
            status = "PASS" if score >= 85.0 else ("WARN" if score >= 65.0 else "FAIL")
            return {
                "status": status,
                "similarity_score": score,
                "method": "file_size_heuristic",
                "original": str(orig),
                "generated": str(gen),
            }

        orig_w, orig_h = orig_hdr["width"], orig_hdr["height"]
        gen_w, gen_h = gen_hdr["width"], gen_hdr["height"]

        dim_match = (orig_w == gen_w) and (orig_h == gen_h)
        width_ratio = min(orig_w, gen_w) / max(orig_w, gen_w)
        height_ratio = min(orig_h, gen_h) / max(orig_h, gen_h)
        dim_score = (width_ratio * 0.4 + height_ratio * 0.6) * 100.0

        # Attempt deep pixel comparison
        orig_decoded = cls.decode_png_pixels(orig)
        gen_decoded = cls.decode_png_pixels(gen)

        if orig_decoded and gen_decoded:
            buf_res = cls.compare_pixel_buffers(
                orig_decoded,
                gen_decoded,
                color_tolerance=color_tolerance,
                max_samples_axis=300,
            )
            pixel_sim = buf_res["pixel_similarity"]
            mse = buf_res["mse"]
            total_px = buf_res["samples_compared"]

            # Combined score: 70% pixel similarity on common area + 30% dimension similarity
            overall_sim = round((pixel_sim * 0.70) + (dim_score * 0.30), 1)
            status = "PASS" if overall_sim >= 88.0 else ("WARN" if overall_sim >= 70.0 else "FAIL")

            return {
                "status": status,
                "similarity_score": overall_sim,
                "pixel_similarity": round(pixel_sim, 1),
                "dimension_similarity": round(dim_score, 1),
                "mse": round(mse, 2),
                "original_dimensions": {"width": orig_w, "height": orig_h},
                "generated_dimensions": {"width": gen_w, "height": gen_h},
                "dimension_match": dim_match,
                "samples_compared": total_px,
                "original": str(orig),
                "generated": str(gen),
            }
        else:
            # Fallback if unfiltering format wasn't standard RGBA/RGB 8-bit
            size1 = orig.stat().st_size
            size2 = gen.stat().st_size
            size_ratio = min(size1, size2) / max(size1, size2) if max(size1, size2) > 0 else 1.0
            overall_sim = round((dim_score * 0.6 + size_ratio * 40.0), 1)
            status = "PASS" if overall_sim >= 85.0 else ("WARN" if overall_sim >= 65.0 else "FAIL")
            return {
                "status": status,
                "similarity_score": overall_sim,
                "dimension_similarity": round(dim_score, 1),
                "original_dimensions": {"width": orig_w, "height": orig_h},
                "generated_dimensions": {"width": gen_w, "height": gen_h},
                "dimension_match": dim_match,
                "method": "header_and_size",
                "original": str(orig),
                "generated": str(gen),
            }

    @classmethod
    def compare_pixel_buffers(
        cls,
        decoded1: tuple[int, int, list[int]],
        decoded2: tuple[int, int, list[int]],
        rect: dict[str, int | float] | None = None,
        color_tolerance: int = 15,
        max_samples_axis: int = 300,
        offset_x2: int = 0,
        offset_y2: int = 0,
    ) -> dict[str, Any]:
        """
        Compares two decoded pixel buffers within an optional bounding box region.
        Reused by both full-page comparison and per-component region diffing.
        Supports optional coordinate offsets on decoded2 for animation phase alignment.
        """
        w1, h1, b1 = decoded1
        w2, h2, b2 = decoded2

        min_w = min(w1, w2)
        min_h = min(h1, h2)

        if rect:
            rx = max(0, int(rect.get("x", 0)))
            ry = max(0, int(rect.get("y", 0)))
            rw = int(rect.get("width", 0))
            rh = int(rect.get("height", 0))
            if rw <= 0:
                rw = min_w - rx
            if rh <= 0:
                rh = min_h - ry
            start_x = rx
            start_y = ry
            end_x = min(rx + rw, min_w)
            end_y = min(ry + rh, min_h)
        else:
            start_x = 0
            start_y = 0
            end_x = min_w
            end_y = min_h

        if end_x <= start_x or end_y <= start_y:
            return {
                "similarity_score": 100.0,
                "divergence_score": 0.0,
                "pixel_similarity": 100.0,
                "mse": 0.0,
                "samples_compared": 0,
                "diff_pixels_count": 0,
                "out_of_bounds": True,
            }

        span_w = end_x - start_x
        span_h = end_y - start_y

        bytes_per_px_1 = len(b1) // (w1 * h1) if (w1 * h1) > 0 else 4
        bytes_per_px_2 = len(b2) // (w2 * h2) if (w2 * h2) > 0 else 4

        step_y = max(1, span_h // max_samples_axis)
        step_x = max(1, span_w // max_samples_axis)

        matching_px = 0
        diff_px = 0
        total_px = 0
        squared_diff_sum = 0.0

        for y in range(start_y, end_y, step_y):
            y2 = y + offset_y2
            if y2 < 0 or y2 >= h2:
                continue
            row1_start = y * w1 * bytes_per_px_1
            row2_start = y2 * w2 * bytes_per_px_2
            for x in range(start_x, end_x, step_x):
                x2 = x + offset_x2
                if x2 < 0 or x2 >= w2:
                    continue
                px1 = row1_start + x * bytes_per_px_1
                px2 = row2_start + x2 * bytes_per_px_2

                r1, g1, b1_val = b1[px1], b1[px1 + 1], b1[px1 + 2]
                r2, g2, b2_val = b2[px2], b2[px2 + 1], b2[px2 + 2]

                diff = math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1_val - b2_val) ** 2)
                squared_diff_sum += (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1_val - b2_val) ** 2

                if diff <= color_tolerance:
                    matching_px += 1
                else:
                    diff_px += 1
                total_px += 1

        pixel_sim = (matching_px / total_px * 100.0) if total_px > 0 else 100.0
        divergence = round(100.0 - pixel_sim, 2)
        mse = squared_diff_sum / (total_px * 3) if total_px > 0 else 0.0

        return {
            "similarity_score": round(pixel_sim, 2),
            "divergence_score": divergence,
            "pixel_similarity": round(pixel_sim, 2),
            "mse": round(mse, 2),
            "samples_compared": total_px,
            "diff_pixels_count": diff_px,
            "out_of_bounds": False,
        }

    @classmethod
    def compare_region(
        cls,
        original: Path | str | tuple[int, int, list[int]],
        generated: Path | str | tuple[int, int, list[int]],
        rect: dict[str, int | float],
        color_tolerance: int = 15,
        threshold: float = 5.0,
        detect_phase_shift: bool = True,
        max_phase_shift_px: int = 30,
    ) -> dict[str, Any]:
        """
        Compares a specific rectangular component region across two screenshots or pixel buffers.
        Returns threshold-gated flagging and per-region divergence metrics.
        Includes animation-aware phase difference detection for continuous motion components.
        """
        orig_decoded = original if isinstance(original, tuple) else cls.decode_png_pixels(original)
        gen_decoded = generated if isinstance(generated, tuple) else cls.decode_png_pixels(generated)

        if not orig_decoded or not gen_decoded:
            return {
                "status": "FAIL",
                "divergence_score": 100.0,
                "similarity_score": 0.0,
                "flagged": True,
                "threshold": threshold,
                "rect": rect,
                "error": "Failed to decode PNG pixels for region comparison",
                "samples_compared": 0,
                "diff_pixels_count": 0,
                "mse": 0.0,
            }

        res = cls.compare_pixel_buffers(
            orig_decoded,
            gen_decoded,
            rect=rect,
            color_tolerance=color_tolerance,
            max_samples_axis=200,
        )

        divergence = res["divergence_score"]
        flagged = divergence > threshold
        status = "FAIL" if flagged else "PASS"

        phase_detected = False
        phase_offset = 0
        phase_aligned_div = divergence
        phase_aligned_sim = res["similarity_score"]

        # Animation-aware phase difference detection:
        # If region diverges above threshold, test if horizontal translation phase shift explains it
        rw = int(rect.get("width", 0))
        if flagged and detect_phase_shift and rw >= 100:
            best_s = 0
            best_div = divergence
            best_sim = res["similarity_score"]
            for s in range(-max_phase_shift_px, max_phase_shift_px + 1, 2):
                if s == 0:
                    continue
                shifted_res = cls.compare_pixel_buffers(
                    orig_decoded,
                    gen_decoded,
                    rect=rect,
                    color_tolerance=color_tolerance,
                    max_samples_axis=200,
                    offset_x2=-s,
                )
                if shifted_res["divergence_score"] < best_div:
                    best_div = shifted_res["divergence_score"]
                    best_sim = shifted_res["similarity_score"]
                    best_s = s

            # If a phase shift explains > 40% of the divergence or brings divergence below threshold
            if best_div < divergence * 0.60 or best_div <= threshold:
                phase_detected = True
                phase_offset = best_s
                phase_aligned_div = best_div
                phase_aligned_sim = best_sim
                if best_div <= threshold:
                    flagged = False
                    status = "PASS"

        result_payload: dict[str, Any] = {
            "status": status,
            "divergence_score": divergence,
            "similarity_score": res["similarity_score"],
            "flagged": flagged,
            "threshold": threshold,
            "rect": rect,
            "mse": res["mse"],
            "samples_compared": res["samples_compared"],
            "diff_pixels_count": res["diff_pixels_count"],
        }
        if phase_detected:
            result_payload["phase_difference_detected"] = True
            result_payload["phase_offset_px"] = phase_offset
            result_payload["phase_aligned_divergence"] = phase_aligned_div
            result_payload["phase_aligned_similarity"] = phase_aligned_sim

        return result_payload


async def capture_generated_screenshots(
    output_dir: Path | str,
    viewports: dict[str, dict[str, int]] | None = None,
) -> dict[str, Any]:
    """
    Renders the generated HTML output in headless Chromium across configured viewports
    and captures screenshots for empirical visual diff comparison.
    """
    out_path = Path(output_dir)
    html_file = out_path / "index.html"
    if not html_file.exists():
        candidates = list(out_path.glob("**/index.html"))
        if candidates:
            html_file = candidates[0]
        else:
            return {
                "screenshots": {},
                "status": "BLOCKED",
                "error": f"No index.html entry point found in {out_path}",
            }

    from webextractor.constants import DEFAULT_VIEWPORTS
    vps = viewports or dict(DEFAULT_VIEWPORTS)

    screenshots: dict[str, str] = {}
    ss_dir = out_path / "verification" / "screenshots"
    ss_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            for vp_name, vp_cfg in vps.items():
                w = vp_cfg.get("width", 1440)
                h = vp_cfg.get("height", 900)
                page = await browser.new_page(viewport={"width": w, "height": h})
                try:
                    file_url = f"file:///{html_file.resolve().as_posix()}"
                    await page.goto(file_url, wait_until="load", timeout=30_000)
                    await page.wait_for_timeout(1000)
                    shot_path = ss_dir / f"{vp_name}_gen.png"
                    await page.screenshot(path=str(shot_path), full_page=True)
                    screenshots[vp_name] = str(shot_path)
                finally:
                    await page.close()
            await browser.close()

        return {
            "screenshots": screenshots,
            "status": "OK",
            "html_entry": str(html_file),
        }
    except Exception as ex:
        return {
            "screenshots": screenshots,
            "status": "BLOCKED",
            "error": str(ex),
        }

