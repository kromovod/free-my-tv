"""Draws the Wi-Fi symbol the way tools/make_symbols.py renders the others: a white PNG with transparency, sized to the
same em, so Symbols.draw() treats it like any Material Symbols icon.

The project's icons come from the Material Symbols Rounded font, which isn't in this repo (make_symbols.py takes it as
an argument). Rather than pull a 300 MB font for one glyph, this draws the same shape by hand: three arcs and the dot on
the font's 24-unit grid, at 172 px per em, anti-aliased by 3x supersampling.

The arcs all span the same angle (the classic Wi-Fi fan), so the gaps between them stay even.

Usage: python make_wifi.py OUT_DIR [EM_PX]
"""
import math
import os
import struct
import sys
import zlib

EM = 172          # tools/make_symbols.py renders a 172 px em; Symbols.PX_PER_POINT expects exactly that
SS = 3            # supersampling factor
GRID = 24.0       # Material Symbols' own grid: the glyph is drawn in 0..24 units

# The fan: center of the arcs (the dot's center), the three radii, the stroke width and the angle each arc spans.
CX, CY = 12.0, 18.4
RADII = (3.8, 7.6, 11.4)
HALF = 1.45       # half the stroke width
FROM, TO = 42.0, 138.0   # degrees, measured from +x going up: symmetric about the vertical


def arc_points(r, samples=400):
    """The stroked arc as a closed polygon: the outer edge out, the inner edge back."""
    outer, inner = [], []
    for i in range(samples + 1):
        a = math.radians(FROM + (TO - FROM) * i / samples)
        dx, dy = math.cos(a), -math.sin(a)
        outer.append((CX + (r + HALF) * dx, CY + (r + HALF) * dy))
        inner.append((CX + (r - HALF) * dx, CY + (r - HALF) * dy))
    return outer + inner[::-1]


def circle(cx, cy, r, samples=360):
    return [(cx + r * math.cos(2 * math.pi * i / samples), cy + r * math.sin(2 * math.pi * i / samples))
            for i in range(samples)]


def inside(px, py, poly):
    """Even-odd point-in-polygon."""
    c = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            x = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < x:
                c = not c
    return c


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "app/assets/symbols"
    em = int(sys.argv[2]) if len(sys.argv) > 2 else EM
    os.makedirs(out, exist_ok=True)

    shapes = [circle(CX, CY, 1.45)] + [arc_points(r) for r in RADII]

    xs = [x for s in shapes for x, _ in s]
    ys = [y for s in shapes for _, y in s]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    scale = em / GRID
    pad = 16 / 8.0                      # make_symbols.py pads 16 px on an 8x canvas, then divides by 8
    w = int(round((maxx - minx) * scale + 2 * pad))
    h = int(round((maxy - miny) * scale + 2 * pad))
    ox = pad - minx * scale
    oy = pad - miny * scale

    polys = [[(ox + x * scale, oy + y * scale) for x, y in s] for s in shapes]

    # Supersample, then box-filter down: the arcs' edges come out as smooth as the font's.
    W, H = w * SS, h * SS
    cov = bytearray(W * H)
    for poly in polys:
        big = [(x * SS, y * SS) for x, y in poly]
        ymin = max(0, int(min(p[1] for p in big)))
        ymax = min(H - 1, int(max(p[1] for p in big)) + 1)
        xmin = max(0, int(min(p[0] for p in big)))
        xmax = min(W - 1, int(max(p[0] for p in big)) + 1)
        for py in range(ymin, ymax + 1):
            row = py * W
            for px in range(xmin, xmax + 1):
                if not cov[row + px] and inside(px + 0.5, py + 0.5, big):
                    cov[row + px] = 1

    alpha = bytearray(w * h)
    denom = SS * SS
    for y in range(h):
        for x in range(w):
            total = 0
            for dy in range(SS):
                row = (y * SS + dy) * W + x * SS
                total += sum(cov[row:row + SS])
            alpha[y * w + x] = total * 255 // denom

    # The app wants white ink on transparency. A preview (third argument "dark") composites it on a dark background so
    # the shape can actually be looked at: white on white reads as an empty image.
    dark = len(sys.argv) > 3 and sys.argv[3] == "dark"
    raw = bytearray()
    for y in range(h):
        raw.append(0)                                    # filter: none
        for x in range(w):
            a = alpha[y * w + x]
            if dark:
                v = 32 + (255 - 32) * a // 255
                raw += bytes((v, v, v))
            else:
                raw += bytes((255, 255, 255, a))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))

    path = os.path.join(out, "wifi.png")
    with open(path, "wb") as f:
        f.write(png)
    print("wrote %s (%dx%d)" % (path, w, h))


if __name__ == "__main__":
    main()
