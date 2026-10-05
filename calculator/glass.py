# -*- coding: utf-8 -*-
"""Frosted-glass button textures built with Gaussian smoothing.

Everything here is pure standard library (no PIL, no numpy) and runs
on both Python 2.7 and Python 3.x, so the glass look is available in
any Tk environment.

A glass tile is a small image computed at start-up:

1. a vertical color gradient (light on top, dark on the bottom);
2. frosted grain: white noise generated at 1/4 resolution, Gaussian
   smoothed with a separable kernel, then bilinearly up-sampled back
   to button size;
3. a specular sheen: a soft band of light near the top edge, also
   Gaussian smoothed;
4. a subtle bevel: brighter along the top/left edges, darker along
   the bottom/right ones, faking refracting glass edges.

The finished tile is RGBA.  On Tcl/Tk 8.6+ it is encoded as PNG
(PhotoImage has supported per-pixel alpha since 8.6); on older Tk
(e.g. the 8.5 shipped with Python 2.7) it is encoded as binary PPM
with the area around the rounded corners pre-composited against the
window background color, so it still reads as glass on the panel.
"""

import math
import random
import struct
import sys
import zlib


def _to_bytes(values):
    """Pack ints (0..255) into a byte string, py2/py3 safe."""
    if sys.version_info[0] >= 3:
        return bytes(values)
    return u"".join(unichr(v) for v in values).encode("latin-1")

# The scene is painted on this small "unit" grid and then bilinearly
# resized to the actual button size.  The pure-Python Gaussian passes
# stay cheap, and the up-sampling itself acts as extra smoothing.
UNIT_W = 64
UNIT_H = 16


def gaussian_kernel(sigma, radius=None):
    """Normalized 1-D Gaussian kernel (odd number of taps)."""
    if sigma <= 0:
        return [1.0]
    if radius is None:
        radius = max(1, int(math.ceil(sigma * 3.0)))
    kernel = [math.exp(-(i * i) / (2.0 * sigma * sigma))
              for i in range(-radius, radius + 1)]
    total = sum(kernel)
    return [value / total for value in kernel]


def _convolve_1d(values, kernel):
    """1-D convolution with edge clamping."""
    n = len(values)
    half = len(kernel) // 2
    out = [0.0] * n
    for x in range(n):
        acc = 0.0
        for j, weight in enumerate(kernel):
            i = x + j - half
            if i < 0:
                i = 0
            elif i >= n:
                i = n - 1
            acc += values[i] * weight
        out[x] = acc
    return out


def gaussian_blur_grid(grid, sigma, radius=None):
    """Separable 2-D Gaussian blur of a grid of floats.

    `grid` is a list of rows, each a list of floats.  One 1-D Gaussian
    kernel is applied to every row and then to every column; because
    the Gaussian is separable, that is exactly a 2-D Gaussian blur.
    """
    kernel = gaussian_kernel(sigma, radius)
    rows = [_convolve_1d(row, kernel) for row in grid]
    columns = [list(column) for column in zip(*rows)]
    columns = [_convolve_1d(column, kernel) for column in columns]
    return [list(row) for row in zip(*columns)]


def _bilinear_upsample(grid, width, height, channels=1):
    """Resize a float grid to width x height (bilinear).

    Each pixel is a float (channels=1) or a list of channel values.
    """
    gh = len(grid)
    gw = len(grid[0])
    out = []
    for y in range(height):
        gy = (y + 0.5) * (gh - 1) / float(height)
        y0 = int(gy)
        y1 = min(y0 + 1, gh - 1)
        fy = gy - y0
        top = grid[y0]
        bottom = grid[y1]
        row = []
        for x in range(width):
            gx = (x + 0.5) * (gw - 1) / float(width)
            x0 = int(gx)
            x1 = min(x0 + 1, gw - 1)
            fx = gx - x0
            if channels == 1:
                a = top[x0] + (top[x1] - top[x0]) * fx
                b = bottom[x0] + (bottom[x1] - bottom[x0]) * fx
                row.append(a + (b - a) * fy)
            else:
                a = [top[x0][c] + (top[x1][c] - top[x0][c]) * fx
                     for c in range(channels)]
                b = [bottom[x0][c] + (bottom[x1][c] - bottom[x0][c]) * fx
                     for c in range(channels)]
                row.append([a[c] + (b[c] - a[c]) * fy for c in range(channels)])
        out.append(row)
    return out


def _paint_scene(seed, top, bottom, sheen_strength, brightness):
    """Paint the glass scene on the unit grid (rows of [r, g, b] floats)."""
    rng = random.Random(seed)
    noise_w = max(1, UNIT_W // 4)
    noise_h = max(1, UNIT_H // 4)
    noise = [[rng.random() for _ in range(noise_w)] for _ in range(noise_h)]
    # Gaussian smoothing turns raw white noise into soft frosted grain.
    grain = _bilinear_upsample(gaussian_blur_grid(noise, 1.1), UNIT_W, UNIT_H)

    sheen = []
    for y in range(UNIT_H):
        falloff = max(0.0, 1.0 - float(y) / (UNIT_H * 0.62))
        sheen.append([falloff ** 1.6] * UNIT_W)
    sheen = gaussian_blur_grid(sheen, 1.4)

    rows = []
    for y in range(UNIT_H):
        t = float(y) / (UNIT_H - 1)
        base = [top[c] + (bottom[c] - top[c]) * t for c in (0, 1, 2)]
        row = []
        for x in range(UNIT_W):
            g = (grain[y][x] - 0.5) * 16.0
            s = sheen[y][x] * 34.0 * sheen_strength
            row.append([base[0] * brightness + g + s,
                        base[1] * brightness + g + s,
                        base[2] * brightness + g + s])
        rows.append(row)
    return rows


def _rounded_mask(x, y, width, height, radius):
    """Anti-aliased coverage (0..1) of a rounded rectangle at (x, y)."""
    radius = min(radius, (width - 1) / 2.0, (height - 1) / 2.0)
    dx = max(radius - x, 0.0, x - (width - 1 - radius))
    dy = max(radius - y, 0.0, y - (height - 1 - radius))
    cover = radius + 0.5 - math.hypot(dx, dy)
    if cover <= 0.0:
        return 0.0
    if cover >= 1.0:
        return 1.0
    return cover


def paint_scene(seed, top, bottom, sheen_strength=1.0, brightness=1.0):
    """The size-independent glass scene (UNIT_W x UNIT_H rows of
    [r, g, b] floats).

    The result depends only on the seed and the colors, never on the
    tile size, so it can be cached once and fed to `tile_from_scene`
    to re-tile a button at any size (e.g. when the window is resized)
    without re-running the Gaussian passes.
    """
    return _paint_scene(seed, top, bottom, sheen_strength, brightness)


def tile_from_scene(scene, width, height, radius, background, alpha):
    """Rasterize a cached unit scene (see `paint_scene`) into a
    width x height RGBA tile with bevel, rounded corners and the
    pre-composited background: rows of (r, g, b, a) ints, 0..255."""
    raster = _bilinear_upsample(scene, width, height, channels=3)
    # The bevel depends on one coordinate at a time, so every part of
    # it is precomputed once per row/column; the per-pixel combination
    # keeps the exact expression of the original renderer.
    top_b = [max(0.0, 1.0 - float(y) / 2.6) * 16.0 for y in range(height)]
    bottom_b = [max(0.0, 1.0 - float(height - 1 - y) / 2.6) * 12.0
                for y in range(height)]
    left_b = [max(0.0, 1.0 - float(x) / 2.6) * 8.0 for x in range(width)]
    right_b = [max(0.0, 1.0 - float(width - 1 - x) / 2.6) * 8.0
               for x in range(width)]
    bg = background
    rows = []
    for y in range(height):
        tb, bb = top_b[y], bottom_b[y]
        raster_row = raster[y]
        row = []
        for x in range(width):
            cover = _rounded_mask(x, y, width, height, radius)
            if cover <= 0.0:
                row.append((int(bg[0]), int(bg[1]), int(bg[2]), 0))
                continue
            bevel = ((tb + left_b[x]) - (bb + right_b[x])) * cover
            a = alpha * cover
            color = []
            for c in range(3):
                v = raster_row[x][c] + bevel
                if v < 0.0:
                    v = 0.0
                elif v > 255.0:
                    v = 255.0
                color.append(v)
            row.append((int(bg[0] * (1.0 - a) + color[0] * a),
                        int(bg[1] * (1.0 - a) + color[1] * a),
                        int(bg[2] * (1.0 - a) + color[2] * a),
                        int(a * 255)))
        rows.append(row)
    return rows


def render_tile(width, height, radius, background, top, bottom, alpha,
                seed, sheen_strength=1.0, brightness=1.0):
    """Render one glass tile: rows of (r, g, b, a) ints, each 0..255.

    `background` is the panel color the tile will sit on; pixels are
    pre-composited against it so the PPM fallback (no alpha channel)
    matches what the PNG path (per-pixel alpha) shows.
    """
    return tile_from_scene(
        paint_scene(seed, top, bottom, sheen_strength, brightness),
        width, height, radius, background, alpha)


def png_bytes(rows):
    """Encode RGBA rows (list of (r, g, b, a) ints) as an 8-bit PNG."""
    width = len(rows[0])
    height = len(rows)

    def chunk(tag, data):
        head = struct.pack(">I", len(data)) + tag
        return head + data + struct.pack(">I", zlib.crc32(head + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + _to_bytes([channel for pixel in row
                                        for channel in pixel]) for row in rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))


def ppm_bytes(rows):
    """Encode RGBA rows as opaque binary PPM (alpha is dropped; the
    pre-composited colors already account for it)."""
    width = len(rows[0])
    height = len(rows)
    body = b"".join(_to_bytes([channel for pixel in row
                               for channel in pixel[:3]]) for row in rows)
    header = ("P6\n%d %d\n255\n" % (width, height)).encode("ascii")
    return header + body


# Per-state parameters shared by every button: (alpha, sheen strength,
# brightness).  Scene-dependent parts (sheen, brightness) belong to
# `paint_scene`; alpha is applied when rasterizing a cached scene.
TILE_STATES = {
    "normal": (0.85, 1.0, 1.0),
    "hover": (0.92, 1.4, 1.07),
    "pressed": (0.97, 0.55, 0.93),
}


def make_kind_tiles(width, height, radius, background, top, bottom, seed):
    """The three interaction states of one button, as RGBA row grids."""
    tiles = {}
    for name, (alpha, sheen, brightness) in TILE_STATES.items():
        tiles[name] = render_tile(width, height, radius, background, top,
                                  bottom, alpha, seed, sheen, brightness)
    return tiles
