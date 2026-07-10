#!/usr/bin/env python3
"""Extract the largest embedded DIB preview from a DWG without a CAD SDK.

The result is visual quality-control evidence only. It must never be treated as
an entity-level extraction or electrical connectivity source of truth.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    return parser.parse_args()


def find_dibs(data: bytes) -> list[tuple[int, int, int, int, int, int, int, int]]:
    found = []
    scan_limit = min(len(data) - 40, 300_000)
    for offset in range(max(scan_limit, 0)):
        if data[offset : offset + 4] != b"\x28\x00\x00\x00":
            continue
        try:
            width, height = struct.unpack_from("<ii", data, offset + 4)
            planes, bits_per_pixel = struct.unpack_from("<HH", data, offset + 12)
            compression, image_size = struct.unpack_from("<II", data, offset + 16)
            colors_used = struct.unpack_from("<I", data, offset + 32)[0]
        except struct.error:
            continue
        if not (
            1 <= abs(width) <= 20_000
            and 1 <= abs(height) <= 20_000
            and planes == 1
            and bits_per_pixel in {1, 4, 8, 16, 24, 32}
            and compression in {0, 1, 2, 3, 4, 5, 6}
        ):
            continue
        row_size = ((abs(width) * bits_per_pixel + 31) // 32) * 4
        expected_size = row_size * abs(height)
        if image_size == 0:
            image_size = expected_size
        if image_size < expected_size // 4 or image_size > expected_size * 4 + 1024:
            continue
        palette_entries = colors_used or ((1 << bits_per_pixel) if bits_per_pixel <= 8 else 0)
        masks = 12 if compression == 3 and bits_per_pixel in {16, 32} else (16 if compression == 6 else 0)
        pixel_relative_offset = 40 + masks + palette_entries * 4
        total_size = pixel_relative_offset + image_size
        if offset + total_size <= len(data):
            found.append(
                (
                    offset,
                    width,
                    height,
                    bits_per_pixel,
                    compression,
                    image_size,
                    pixel_relative_offset,
                    total_size,
                )
            )
    return found


def extract(source: Path, target: Path) -> dict[str, int | str]:
    data = source.read_bytes()
    candidates = find_dibs(data)
    if not candidates:
        raise ValueError(f"No embedded DIB preview found in {source}")
    candidate = max(candidates, key=lambda item: (abs(item[1] * item[2]), -item[0]))
    offset, width, height, bpp, compression, image_size, pixel_offset, total_size = candidate
    dib = data[offset : offset + total_size]
    bitmap_header = struct.pack("<2sIHHI", b"BM", 14 + len(dib), 0, 0, 14 + pixel_offset)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(bitmap_header + dib)
    return {
        "input": str(source),
        "output": str(target),
        "offset": offset,
        "width": width,
        "height": height,
        "bits_per_pixel": bpp,
        "compression": compression,
        "image_size": image_size,
        "candidate_count": len(candidates),
    }


def main() -> int:
    args = parse_args()
    print(json.dumps(extract(args.input, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
