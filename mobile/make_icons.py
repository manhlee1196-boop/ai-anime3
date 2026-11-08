#!/usr/bin/env python3
"""Sinh icon PNG cho app (không cần Pillow — chỉ stdlib zlib/struct).

Chạy lại khi muốn đổi màu/logo:

    python3 mobile/make_icons.py

Sinh ra mobile/app/icons/: icon-192.png, icon-512.png, maskable-512.png,
apple-touch-icon.png. Icon maskable để logo nằm trong vùng an toàn 80% nên
Android cắt tròn/khoét lỗ vẫn không mất hình.
"""

import math
import struct
import sys
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent / "app" / "icons"

# Bảng màu: tím anime -> hồng (giống gradient của app).
TOP = (124, 92, 255)
BOTTOM = (255, 92, 138)
DARK = (11, 13, 18)


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def rounded_rect_alpha(x, y, size, radius):
    """Độ phủ 0..1 của hình vuông bo góc; viền mềm 1 px để không bị răng cưa."""
    cx = min(max(x + 0.5, radius), size - radius)
    cy = min(max(y + 0.5, radius), size - radius)
    distance = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
    return max(0.0, min(1.0, radius + 0.5 - distance))


def star_alpha(x, y, size, cx, cy, radius, sharpness=0.62):
    """Sao 4 cánh (astroid) — cùng hình với logo trên thanh tiêu đề."""
    u = abs((x + 0.5 - cx) / radius)
    v = abs((y + 0.5 - cy) / radius)
    if u > 1.2 or v > 1.2:
        return 0.0
    value = (u ** sharpness) + (v ** sharpness)
    return max(0.0, min(1.0, (1.0 - value) * 6.0))


def pixel(x, y, size, maskable=False):
    if maskable:
        # Nền phủ kín (Android tự cắt), logo nhỏ hơn để không bị xoá góc.
        base = lerp(TOP, BOTTOM, (x + y) / (2 * size))
        alpha = 1.0
        inner = size * 0.27
    else:
        base = lerp(TOP, BOTTOM, (x + y) / (2 * size))
        alpha = rounded_rect_alpha(x, y, size, size * 0.23)
        inner = size * 0.29

    star = star_alpha(x, y, size, size * 0.5, size * 0.46, inner)
    glow = star_alpha(x, y, size, size * 0.5, size * 0.46, inner * 1.55, sharpness=0.5) * 0.12
    colour = base
    if glow:
        colour = lerp(colour, (255, 255, 255), min(1.0, glow))
    if star:
        colour = lerp(colour, (255, 255, 255), min(1.0, star))
    # chấm nhỏ dưới ngôi sao: nhịp anime
    dot = math.hypot(x + 0.5 - size * 0.70, y + 0.5 - size * 0.70)
    dot_r = size * 0.05
    if dot <= dot_r + 1:
        colour = lerp(colour, (255, 255, 255), max(0.0, min(1.0, dot_r + 0.5 - dot)))
    return (*colour, round(alpha * 255))


def write_png(path, size, maskable=False):
    raw = bytearray()
    for y in range(size):
        raw.append(0)                      # filter type 0 cho mỗi hàng
        for x in range(size):
            raw.extend(pixel(x, y, size, maskable))
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)   # 8-bit RGBA
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", header)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)
    return len(png)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    targets = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("maskable-512.png", 512, True),
        ("apple-touch-icon.png", 180, True),
    ]
    for name, size, maskable in targets:
        written = write_png(OUT / name, size, maskable)
        print(f"✅ {name}: {size}×{size} · {written / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
