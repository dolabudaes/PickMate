from __future__ import annotations

import hashlib
import struct
import zlib

from ..db import AUTHORIZED_CATEGORY, product_one

BRAND_COLORS = {
    "soundcore": ("#1C1C1C", "#FF6A3D"),
    "redmi": ("#2B2B2B", "#FF6900"),
    "oppo": ("#1F3A2E", "#2EC48A"),
    "oneplus": ("#1A1A1A", "#EB0028"),
    "realme": ("#2A2410", "#F5C518"),
    "huawei": ("#2A1014", "#CF0A2C"),
    "moondrop": ("#20242C", "#8FA4C8"),
    "edifier": ("#2A1216", "#C41E3A"),
    "jbl": ("#26180C", "#FF6600"),
    "sony": ("#141414", "#4A90D9"),
    "honor": ("#102038", "#3D7EFF"),
    "nothing": ("#1A1A1A", "#D8D8D8"),
}


def catalog_image_png(token: str) -> bytes:
    product = lookup_product(token)
    brand = str((product or {}).get("brand") or token.replace("-", " "))
    ink, accent = colors_for(brand, token)
    return render_speaker_png(parse_hex(ink), parse_hex(accent))


def lookup_product(token: str) -> dict | None:
    cleaned = token.strip()
    try:
        return product_one(
            "SELECT product_id, brand, title FROM products WHERE product_id=? AND main_category=?",
            (cleaned, AUTHORIZED_CATEGORY),
        )
    except Exception:
        return None


def colors_for(brand: str, token: str) -> tuple[str, str]:
    key = brand.lower()
    if key in BRAND_COLORS:
        return BRAND_COLORS[key]
    digest = hashlib.md5(f"{brand}:{token}".encode()).hexdigest()
    return f"#{digest[:6]}", f"#{digest[6:12]}"


def parse_hex(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def render_speaker_png(ink: tuple[int, int, int], accent: tuple[int, int, int], size: int = 320) -> bytes:
    bg = (247, 244, 240)
    pixels = [bg] * (size * size)

    def set_pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < size and 0 <= y < size:
            pixels[y * size + x] = color

    def fill_round_rect(x0: int, y0: int, x1: int, y1: int, radius: int, color: tuple[int, int, int]) -> None:
        for y in range(y0, y1):
            for x in range(x0, x1):
                dx = min(x - x0, x1 - 1 - x)
                dy = min(y - y0, y1 - 1 - y)
                if dx < radius and dy < radius and (radius - dx) ** 2 + (radius - dy) ** 2 > radius ** 2:
                    continue
                set_pixel(x, y, color)

    def fill_circle(cx: int, cy: int, radius: int, color: tuple[int, int, int]) -> None:
        r2 = radius * radius
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r2:
                    set_pixel(x, y, color)

    fill_round_rect(48, 168, 272, 228, 18, ink)
    fill_round_rect(60, 180, 260, 216, 12, (18, 18, 18))
    for cx in (96, 160, 224):
        fill_circle(cx, 198, 10, accent)
    fill_round_rect(70, 78, 138, 152, 16, ink)
    fill_circle(104, 115, 22, accent)
    fill_circle(104, 115, 8, (17, 17, 17))
    fill_round_rect(182, 78, 250, 152, 16, ink)
    fill_circle(216, 115, 22, accent)
    fill_circle(216, 115, 8, (17, 17, 17))
    return encode_png(size, size, pixels)


def encode_png(width: int, height: int, pixels: list[tuple[int, int, int]]) -> bytes:
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixels[y * width + x])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return b"".join([
        b"\x89PNG\r\n\x1a\n",
        chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
        chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
        chunk(b"IEND", b""),
    ])
