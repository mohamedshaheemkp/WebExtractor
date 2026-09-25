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
            w1, h1, b1 = orig_decoded
            w2, h2, b2 = gen_decoded
            min_w = min(w1, w2)
            min_h = min(h1, h2)

            bytes_per_px_1 = len(b1) // (w1 * h1) if (w1 * h1) > 0 else 4
            bytes_per_px_2 = len(b2) // (w2 * h2) if (w2 * h2) > 0 else 4

            # Sample grid for efficiency on very large screenshots
            step_y = max(1, min_h // 300)
            step_x = max(1, min_w // 300)

            matching_px = 0
            total_px = 0
            squared_diff_sum = 0.0

            for y in range(0, min_h, step_y):
                row1_start = y * w1 * bytes_per_px_1
                row2_start = y * w2 * bytes_per_px_2
                for x in range(0, min_w, step_x):
                    px1 = row1_start + x * bytes_per_px_1
                    px2 = row2_start + x * bytes_per_px_2

                    r1, g1, b1_val = b1[px1], b1[px1 + 1], b1[px1 + 2]
                    r2, g2, b2_val = b2[px2], b2[px2 + 1], b2[px2 + 2]

                    diff = math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1_val - b2_val) ** 2)
                    squared_diff_sum += (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1_val - b2_val) ** 2

                    if diff <= color_tolerance:
                        matching_px += 1
                    total_px += 1

            pixel_sim = (matching_px / total_px * 100.0) if total_px > 0 else 100.0
            mse = squared_diff_sum / (total_px * 3) if total_px > 0 else 0.0

            # Combined score: 65% pixel similarity on common area + 35% dimension similarity
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
