# -*- coding: utf-8 -*-
import os
import struct
import sys
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculator import glass


class GaussianKernelTests(unittest.TestCase):
    def test_normalized(self):
        for sigma in (0.5, 1.0, 2.5):
            kernel = glass.gaussian_kernel(sigma)
            self.assertAlmostEqual(sum(kernel), 1.0, places=9)

    def test_symmetric_and_odd(self):
        kernel = glass.gaussian_kernel(1.5)
        self.assertEqual(len(kernel) % 2, 1)
        self.assertEqual(kernel, kernel[::-1])

    def test_center_is_peak(self):
        kernel = glass.gaussian_kernel(1.0)
        mid = len(kernel) // 2
        self.assertEqual(max(kernel), kernel[mid])
        for i in range(mid, len(kernel) - 1):
            self.assertGreaterEqual(kernel[i], kernel[i + 1])

    def test_zero_sigma_is_delta(self):
        self.assertEqual(glass.gaussian_kernel(0), [1.0])


class GaussianBlurTests(unittest.TestCase):
    def test_constant_stays_constant(self):
        grid = [[5.0] * 9 for _ in range(7)]
        out = glass.gaussian_blur_grid(grid, 1.0)
        self.assertEqual(len(out), 7)
        for row in out:
            self.assertEqual(len(row), 9)
            for value in row:
                self.assertAlmostEqual(value, 5.0, places=6)

    def test_impulse_spreads_and_fades(self):
        grid = [[0.0] * 11 for _ in range(11)]
        grid[5][5] = 100.0
        out = glass.gaussian_blur_grid(grid, 1.2)
        self.assertGreater(out[5][5], 0.0)
        self.assertGreater(out[4][5], 0.0)  # neighbours pick up energy
        self.assertGreater(out[5][5], out[4][5])
        self.assertGreater(out[4][5], out[3][5])  # fades with distance

    def test_mass_is_conserved(self):
        grid = [[0.0] * 11 for _ in range(11)]
        grid[5][5] = 100.0
        out = glass.gaussian_blur_grid(grid, 1.2)
        total = 0.0
        for row in out:
            total += sum(row)
        self.assertAlmostEqual(total, 100.0, places=2)

    def test_blur_reduces_fine_grain(self):
        import random
        rng = random.Random(7)
        grid = [[rng.random() for _ in range(32)] for _ in range(32)]
        out = glass.gaussian_blur_grid(grid, 1.5)

        def neighbor_variation(g):
            total = 0.0
            count = 0
            for y in range(1, len(g) - 1):
                for x in range(1, len(g[0]) - 1):
                    total += abs(g[y][x] - g[y - 1][x])
                    total += abs(g[y][x] - g[y][x - 1])
                    count += 2
            return total / float(count)

        self.assertLess(neighbor_variation(out), neighbor_variation(grid))


class TileTests(unittest.TestCase):
    BG = (23, 24, 33)
    TOP = (92, 95, 112)
    BOTTOM = (31, 33, 42)

    def test_shape_and_ranges(self):
        rows = glass.render_tile(70, 46, 12, self.BG, self.TOP, self.BOTTOM,
                                 0.9, seed=1)
        self.assertEqual(len(rows), 46)
        for row in rows:
            self.assertEqual(len(row), 70)
            for pixel in row:
                self.assertEqual(len(pixel), 4)
                for value in pixel:
                    self.assertTrue(0 <= value <= 255)

    def test_corners_transparent_center_opaque(self):
        rows = glass.render_tile(70, 46, 12, self.BG, self.TOP, self.BOTTOM,
                                 0.9, seed=1)
        self.assertEqual(rows[0][0][3], 0)
        self.assertEqual(rows[0][-1][3], 0)
        self.assertGreater(rows[23][35][3], 0)

    def test_deterministic(self):
        a = glass.render_tile(70, 46, 12, self.BG, self.TOP, self.BOTTOM,
                              0.9, seed=42)
        b = glass.render_tile(70, 46, 12, self.BG, self.TOP, self.BOTTOM,
                              0.9, seed=42)
        self.assertEqual(a, b)

    def test_states_have_different_alpha(self):
        tiles = glass.make_kind_tiles(70, 46, 12, self.BG, self.TOP, self.BOTTOM, 7)
        self.assertEqual(sorted(tiles), ["hover", "normal", "pressed"])
        alpha = lambda rows: sum(sum(p[3] for p in row) for row in rows)
        self.assertLess(alpha(tiles["normal"]), alpha(tiles["hover"]))
        self.assertLess(alpha(tiles["hover"]), alpha(tiles["pressed"]))

    def test_transparent_pixels_match_background(self):
        rows = glass.render_tile(40, 30, 8, self.BG, self.TOP, self.BOTTOM,
                                 0.9, seed=5)
        for row in rows:
            for r, g, b, a in row:
                if a == 0:
                    self.assertEqual((r, g, b), self.BG)


class SceneTests(unittest.TestCase):
    """The size-independent scene API used to re-tile buttons at any
    size when the GUI window is resized."""
    BG = (23, 24, 33)
    TOP = (92, 95, 112)
    BOTTOM = (31, 33, 42)

    def test_scene_shape_and_determinism(self):
        scene = glass.paint_scene(7, self.TOP, self.BOTTOM)
        self.assertEqual(len(scene), glass.UNIT_H)
        for row in scene:
            self.assertEqual(len(row), glass.UNIT_W)
            for pixel in row:
                self.assertEqual(len(pixel), 3)
        self.assertEqual(scene, glass.paint_scene(7, self.TOP, self.BOTTOM))

    def test_scene_is_size_independent(self):
        # The same scene rasterizes at any tile size: the cached scene
        # must never depend on width/height.
        scene = glass.paint_scene(11, self.TOP, self.BOTTOM)
        a = glass.tile_from_scene(scene, 50, 30, 8, self.BG, 0.9)
        b = glass.tile_from_scene(scene, 90, 60, 14, self.BG, 0.9)
        self.assertEqual(len(a), 30)
        self.assertEqual(len(a[0]), 50)
        self.assertEqual(len(b), 60)
        self.assertEqual(len(b[0]), 90)

    def test_roundtrip_matches_render_tile(self):
        for (w, h, rad) in ((70, 46, 12), (56, 38, 10), (98, 64, 17),
                            (150, 46, 12), (70, 100, 12)):
            scene = glass.paint_scene(42, self.TOP, self.BOTTOM, 1.2, 1.05)
            via_scene = glass.tile_from_scene(scene, w, h, rad,
                                              self.BG, 0.9)
            direct = glass.render_tile(w, h, rad, self.BG, self.TOP,
                                       self.BOTTOM, 0.9, seed=42,
                                       sheen_strength=1.2, brightness=1.05)
            self.assertEqual(via_scene, direct)

    def test_kind_tiles_via_states_and_scenes(self):
        tiles = glass.make_kind_tiles(60, 40, 10, self.BG, self.TOP,
                                      self.BOTTOM, 9)
        self.assertEqual(sorted(tiles), ["hover", "normal", "pressed"])
        for name, (alpha, sheen, brightness) in glass.TILE_STATES.items():
            scene = glass.paint_scene(9, self.TOP, self.BOTTOM, sheen,
                                      brightness)
            self.assertEqual(glass.tile_from_scene(scene, 60, 40, 10,
                                                   self.BG, alpha),
                             tiles[name])


class EncoderTests(unittest.TestCase):
    BG = (23, 24, 33)

    def _rows(self):
        return glass.render_tile(24, 16, 8, self.BG,
                                 (92, 95, 112), (31, 33, 42), 0.9, seed=3)

    def test_png_signature_and_payload(self):
        rows = self._rows()
        data = glass.png_bytes(rows)
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        pos = data.find(b"IDAT")
        self.assertGreater(pos, 0)
        length = struct.unpack(">I", data[pos - 4:pos])[0]
        raw = zlib.decompress(data[pos + 4:pos + 4 + length])
        self.assertEqual(len(raw), 16 * (1 + 24 * 4))
        zero = b"\x00"[0]  # byte 0 on py2 and py3 alike
        self.assertEqual(raw[0], zero)  # row 0, filter type "none"
        self.assertEqual(raw[4], zero)  # top-left pixel: alpha 0
        mid = 1 + 8 * (1 + 24 * 4) + 12 * 4
        self.assertGreater(raw[mid + 3], zero)  # center pixel: alpha > 0

    def test_ppm_header_and_size(self):
        rows = self._rows()
        data = glass.ppm_bytes(rows)
        header = "P6\n24 16\n255\n".encode("ascii")
        self.assertTrue(data.startswith(header))
        self.assertEqual(len(data), len(header) + 24 * 16 * 3)


if __name__ == "__main__":
    unittest.main()
