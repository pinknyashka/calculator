# -*- coding: utf-8 -*-
"""Tkinter graphical interface: digit buttons, + - * /, and =.

Run with `python -m calculator.gui` (or `python calculator\gui.py`).

Buttons are drawn as frosted-glass tiles: each tile is a small image
computed at start-up by `calculator.glass` from a color gradient plus
Gaussian-smoothed frosted grain and a specular sheen (a 2-D Gaussian
blur applied with a separable kernel).  On Tcl/Tk 8.6+ (Python 3) the
tiles are PNGs with per-pixel alpha; on older Tk (Python 2.7 ships
8.5) they are pre-composited PPM images.  The glass style works with
or without `customtkinter` (which, if installed, still provides the
root window); if anything is unavailable the GUI falls back to a
plain dark Tkinter theme (standard library only, works on Python 2.7).

The window is adaptive: it can be resized within a limited range
(`MIN_SCALE`..`MAX_SCALE` of the base size) and every element follows
proportionally — buttons stretch, fonts and the display scale, and the
glass tiles are re-rendered for the new sizes (the size-independent
scene is cached, see `calculator.glass.paint_scene`).
"""

from __future__ import print_function

import base64
import os
import shutil
import tempfile

try:
    import tkinter as tk
    import tkinter.font as tkfont
except ImportError:  # Python 2
    import Tkinter as tk
    import tkFont as tkfont

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    ctk = None
    HAS_CTK = False

try:
    from .engine import CalculatorEngine
    from .glass import (TILE_STATES, paint_scene, tile_from_scene,
                        png_bytes, ppm_bytes)
except ImportError:  # direct script execution
    from engine import CalculatorEngine
    from glass import (TILE_STATES, paint_scene, tile_from_scene,
                       png_bytes, ppm_bytes)


# Glass palette: window background, button border, label colors and
# per-button-kind (base, hover) colors.
PALETTE = {
    "window": "#241a10",
    "border": "#4d3a22",
    "formula": "#a08050",
    "display": "#ffffff",
    "digit": ("#33261a", "#453322"),
    "dot": ("#33261a", "#453322"),
    "operator": ("#4a3520", "#5e452a"),
    "equals": ("#d97a1e", "#f0952e"),
    "clear": ("#402420", "#54302a"),
    "backspace": ("#402420", "#54302a"),
}

DIGIT_WIDTH = 70
CELL_PAD = 3  # padx per button side
BUTTON_HEIGHT = 46
CORNER_RADIUS = 12
# The window is resizable within this limited range around its base
# (default) size; MIN_SCALE is the smallest, MAX_SCALE the largest
# allowed window size, as fractions of the base size.
MIN_SCALE = 0.8
MAX_SCALE = 1.5


def _hex_to_rgb(value):
    value = value.lstrip(u"#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def _mix(rgb, other, t):
    """Linear blend of two RGB colors (t in 0..1)."""
    return tuple(int(rgb[i] + (other[i] - rgb[i]) * t) for i in (0, 1, 2))


def _supports_png_alpha():
    """True on Tcl/Tk 8.6+, whose PhotoImage reads per-pixel-alpha PNGs.

    Python 2's Tkinter exposes TkVersion as a float (8.5); Python 3's
    as a string ("8.6").
    """
    version = tk.TkVersion
    if isinstance(version, float):  # Python 2
        return version >= 8.6
    try:
        major, minor = (int(part) for part in str(version).split(u".")[:2])
    except ValueError:
        return False
    return (major, minor) >= (8, 6)


def _dpi_scale(root):
    """Display scaling factor (1.0 at 96 DPI).

    In DPI-aware processes winfo_fpixels reports the real DPI; in
    DPI-unaware ones it reports 96 and Windows stretches the window
    uniformly, so 1.0 is correct there as well.  With customtkinter
    present we follow its scaling factor so raw tk widgets stay in
    sync with the CTk ones.
    """
    if HAS_CTK:
        try:
            factor = ctk.get_scaling_factor()
            if factor and factor > 0:
                return float(factor)
        except Exception:
            pass
    try:
        px_per_inch = root.winfo_fpixels("1i")
        if px_per_inch > 0:
            return px_per_inch / 96.0
    except tk.TclError:
        pass
    return 1.0


def _pick_family(root):
    """First monospace-ish family actually known to this Tk build."""
    try:
        available = set(root.tk.call("font", "families"))
    except tk.TclError:
        return "Consolas"
    for family in ("Consolas", "Cascadia Mono", "DejaVu Sans Mono",
                   "Menlo", "Courier New", "Courier", "Arial"):
        if family in available:
            return family
    return "Consolas"


class GlassButton(object):
    """A canvas-drawn glass button: a Gaussian-smoothed tile + label.

    Tk cannot blur the pixels behind a widget, so the "backdrop" light
    is synthesized inside the tile itself (see calculator.glass); the
    hover and pressed states are pre-rendered tile variants.
    """

    def __init__(self, parent, text, images, label_color, font, background,
                 command):
        self._command = command
        self._images = images
        self._hover = False
        self._down = False
        width = images[u"normal"].width()
        height = images[u"normal"].height()
        self._cw = width
        self._ch = height
        self.canvas = tk.Canvas(parent, width=width, height=height,
                                highlightthickness=0, bd=0,
                                bg=background, cursor=u"hand2")
        self._image_id = self.canvas.create_image(0, 0, anchor=u"nw",
                                                   image=images[u"normal"])
        self._text_id = self.canvas.create_text(width // 2, height // 2,
                                                text=text, font=font,
                                                fill=label_color)
        self.canvas.bind(u"<Enter>", self._on_enter)
        self.canvas.bind(u"<Leave>", self._on_leave)
        self.canvas.bind(u"<ButtonPress-1>", self._on_press)
        self.canvas.bind(u"<ButtonRelease-1>", self._on_release)

    def set_geometry(self, width, height, font=None):
        """Resize the canvas (the adaptive layout calls this whenever
        the window is resized); tile and label are re-centered."""
        self._cw = width
        self._ch = height
        self.canvas.configure(width=width, height=height)
        if font is not None:
            self.canvas.itemconfig(self._text_id, font=font)
        self._paint()

    def retile(self, images):
        """Swap in freshly rendered tiles of the new size (the slow
        part of a resize, done after the geometry already follows)."""
        self._images = images
        self._paint()

    def _paint(self):
        if self._down:
            name = u"pressed"
        elif self._hover:
            name = u"hover"
        else:
            name = u"normal"
        image = self._images[name]
        self.canvas.itemconfig(self._image_id, image=image)
        # Keep tile and label centered: a tile of the previous size
        # stays put while the window moves, until it is re-rendered.
        x = (self._cw - image.width()) // 2
        y = (self._ch - image.height()) // 2
        self.canvas.coords(self._image_id, x, y)
        self.canvas.coords(self._text_id, self._cw // 2, self._ch // 2)

    def _on_enter(self, event):
        self._hover = True
        self._paint()

    def _on_leave(self, event):
        self._hover = False
        self._paint()

    def _on_press(self, event):
        self._down = True
        self._paint()

    def _on_release(self, event):
        clicked = self._down and self._hover
        self._down = False
        self._paint()
        if clicked:
            self._command()


class CalculatorApp(object):
    LAYOUT = [
        (u"C", "clear", 0, 0, 1),
        (u"←", "backspace", 0, 1, 1),
        (u"/", "operator", 0, 2, 1),
        (u"=", "equals", 0, 3, 1),
        (u"7", "digit", 1, 0, 1),
        (u"8", "digit", 1, 1, 1),
        (u"9", "digit", 1, 2, 1),
        (u"*", "operator", 1, 3, 1),
        (u"4", "digit", 2, 0, 1),
        (u"5", "digit", 2, 1, 1),
        (u"6", "digit", 2, 2, 1),
        (u"-", "operator", 2, 3, 1),
        (u"1", "digit", 3, 0, 1),
        (u"2", "digit", 3, 1, 1),
        (u"3", "digit", 3, 2, 1),
        (u"+", "operator", 3, 3, 1),
        (u"0", "digit", 4, 0, 3),
        (u".", "dot", 4, 3, 1),
        (u"pow", "operator", 5, 0, 2),
        (u"sqrt", "operator", 5, 2, 2),
    ]

    def __init__(self, root):
        self.root = root
        self.engine = CalculatorEngine()
        self._glass_tmp = None
        self._key_photos = {}    # (kind, span) -> {state: PhotoImage}
        self._key_buttons = {}   # (kind, span) -> [GlassButton, ...]
        self._scenes = {}        # (kind, span, state) -> cached unit scene
        self._tile_key_order = []
        self._rebuild_queue = []
        self._tile_generation = 0
        self._resize_job = None
        self._rebuild_job = None
        self._bw = 0             # current single-column tile size (px)
        self._bh = 0
        self._bw_rendered = 0    # size the tile images were rendered at
        self._bh_rendered = 0
        self._radius = 0
        self._margin = 0
        self._pad = 0
        self._bg_rgb = (0, 0, 0)
        self._panel = None
        self._glass_active = False
        self._formula_box = None
        self._display_box = None
        self._base_panel_w = 0
        self._plain_sizes = None
        self._plain_buttons = []  # keep plain-theme button refs alive
        self._buttons = []        # keep GlassButton bindings/commands alive
        root.title(u"Калькулятор")
        try:
            self._build_glass()
        except Exception:
            if self._glass_tmp is not None:
                shutil.rmtree(self._glass_tmp, ignore_errors=True)
                self._glass_tmp = None
            for photos in self._key_photos.values():
                for photo in photos.values():
                    destroy = getattr(photo, 'destroy', None)
                    if destroy is not None:
                        try:
                            destroy()
                        except tk.TclError:
                            pass
            self._key_photos = {}
            self._key_buttons = {}
            self._scenes = {}
            self._tile_key_order = []
            self._bw = 0
            self._bh = 0
            self._build_plain()
        self._enable_resizing()

    # --- adaptive window ---

    def _enable_resizing(self):
        """Make the window adaptive: it may grow and shrink within a
        limited range around its base (default) size, and every element
        follows while keeping its relative position."""
        self.root.update_idletasks()
        try:
            base_w = self.root.winfo_reqwidth()
            base_h = self.root.winfo_reqheight()
        except tk.TclError:
            return
        if base_w < 4 or base_h < 4:
            return
        try:
            self.root.resizable(True, True)
            self.root.minsize(int(base_w * MIN_SCALE),
                              int(base_h * MIN_SCALE))
            self.root.maxsize(int(base_w * MAX_SCALE),
                              int(base_h * MAX_SCALE))
        except tk.TclError:
            pass
        if self._panel is not None:
            self._panel.bind(u"<Configure>", self._on_resize)

    # --- layouts ---

    def _make_text_box(self, parent, background):
        """A frame hosting one line of text.  Its grid row carries a
        stretch weight, so the display area follows the window resize;
        the label is pinned inside it."""
        return tk.Frame(parent, bg=background)

    def _build_glass(self):
        """Frosted-glass layout: canvas buttons painted with Gaussian-
        smoothed tiles from calculator.glass (works with or without
        customtkinter)."""
        if HAS_CTK and isinstance(self.root, ctk.CTk):
            ctk.set_appearance_mode("dark")
            self.root.configure(fg_color=PALETTE["window"])
        else:
            self.root.configure(bg=PALETTE["window"])
        try:
            self.root.attributes("-alpha", 0.95)  # window translucency
        except tk.TclError:
            pass

        background = PALETTE["window"]
        bg_rgb = _hex_to_rgb(background)

        # Scale every pixel dimension by the display factor so tiles,
        # gaps and fonts grow together on high-DPI screens; fonts are
        # pixel-sized (negative) and proportional to the tile, so a
        # label can never outgrow its button at any scaling.
        scale = _dpi_scale(self.root)
        family = _pick_family(self.root)
        bw = max(24, int(round(DIGIT_WIDTH * scale)))
        bh = max(24, int(round(BUTTON_HEIGHT * scale)))
        rad = max(2, int(round(CORNER_RADIUS * scale)))
        pad = max(1, int(round(CELL_PAD * scale)))
        margin = max(2, int(round(10 * scale)))
        font_button = (family, -max(8, int(round(bh * 0.46))), u"bold")
        self._font_family = family
        display_size = -max(14, int(round(bh * 0.80)))
        formula_size = -max(9, int(round(bh * 0.40)))
        self._display_base = display_size
        self._formula_base = formula_size
        # Fonts kept around to measure text width (see _fit_text).
        self._display_font = tkfont.Font(self.root, family=family,
                                         size=display_size, weight=u"bold")
        self._formula_font = tkfont.Font(self.root, family=family,
                                         size=formula_size)

        # Cache every unique size-independent unit scene (pure pixel
        # math, no widgets yet, so a failure here falls back to the
        # plain theme cleanly).  The scenes never depend on the tile
        # size, which is what makes re-rendering on window resize cheap
        # enough: only the final rasterization has to be redone.
        seen = set()
        for text, kind, row, col, span in self.LAYOUT:
            key = (kind, span)
            if key in seen:
                continue
            seen.add(key)
            self._tile_key_order.append(key)
            fg = _hex_to_rgb(PALETTE[kind][0])
            top = _mix(fg, (255, 255, 255), 0.22)
            bottom = _mix(fg, (0, 0, 0), 0.16)
            # The seed must not depend on the pixel width, otherwise
            # the grain pattern would change every time the window is
            # resized; span still gives wide tiles their own pattern.
            seed = 131 * len(kind) + 17 * span
            for state, (alpha, sheen, brightness) in TILE_STATES.items():
                self._scenes[(kind, span, state)] = paint_scene(
                    seed, top, bottom, sheen, brightness)

        self._png_ok = _supports_png_alpha()
        self._photo_count = 0
        self._glass_tmp = tempfile.mkdtemp(prefix=u"calc-glass-")
        self._bw = bw
        self._bh = bh
        self._bw_rendered = bw
        self._bh_rendered = bh
        self._radius = rad
        self._margin = margin
        self._pad = pad
        self._bg_rgb = bg_rgb
        self._glass_active = True
        for key in self._tile_key_order:
            self._render_key_photos(key)

        panel = tk.Frame(self.root, bg=background)
        panel.pack(padx=margin, pady=margin, fill=u"both", expand=True)
        for col in range(4):
            panel.grid_columnconfigure(col, weight=1, uniform=u"button")
        for row in range(8):  # 2 text lines + 6 button rows
            panel.grid_rowconfigure(row, weight=1)
        self._panel = panel

        self.formula_var = tk.StringVar(value=u"")
        self._formula_box = self._make_text_box(panel, background)
        self._formula_box.grid(row=0, column=0, columnspan=4, sticky=u"nsew")
        self.formula_label = tk.Label(self._formula_box,
                                      textvariable=self.formula_var,
                                      anchor=u"e",
                                      font=(family, formula_size),
                                      fg=PALETTE["formula"], bg=background)
        self.formula_label.pack(fill=u"both", expand=True)

        self.display_var = tk.StringVar(value=u"0")
        self._display_box = self._make_text_box(panel, background)
        self._display_box.grid(row=1, column=0, columnspan=4,
                               sticky=u"nsew", pady=(0, margin))
        self.display_label = tk.Label(self._display_box,
                                      textvariable=self.display_var,
                                      anchor=u"e",
                                      font=(family, display_size, u"bold"),
                                      fg=PALETTE["display"], bg=background)
        self.display_label.pack(fill=u"both", expand=True)

        for text, kind, row, col, span in self.LAYOUT:
            key = (kind, span)
            button = GlassButton(panel, text, self._key_photos[key], u"white",
                                 font_button, background,
                                 command=lambda k=kind, t=text: self._handle(k, t))
            self._buttons.append(button)
            self._key_buttons.setdefault(key, []).append(button)
            button.canvas.grid(row=2 + row, column=col, columnspan=span,
                               padx=pad, pady=pad)

        self.root.update_idletasks()
        self.root.geometry("%dx%d" % (self.root.winfo_reqwidth(),
                                      self.root.winfo_reqheight()))

    def _make_photo(self, png_data, ppm_data):
        """PhotoImage for one tile: PNG on Tk >= 8.6 (per-pixel alpha),
        otherwise a pre-composited PPM written to a temp file."""
        if self._png_ok:
            try:
                return tk.PhotoImage(master=self.root,
                                     data=base64.b64encode(png_data).decode("ascii"))
            except tk.TclError:
                pass
        path = os.path.join(self._glass_tmp, u"tile%02d.ppm" % self._photo_count)
        self._photo_count += 1
        handle = open(path, "wb")
        try:
            handle.write(ppm_data)
        finally:
            handle.close()
        return tk.PhotoImage(master=self.root, file=path)

    # --- resize handling ---

    def _on_resize(self, event):
        """The panel was resized (i.e. the window was).  One debounced
        pass per drag, not one per pixel."""
        if self._resize_job is not None:
            try:
                self.root.after_cancel(self._resize_job)
            except tk.TclError:
                pass
        self._resize_job = self.root.after(30, self._apply_resize)

    def _apply_resize(self):
        self._resize_job = None
        if self._panel is None:
            return
        panel_w = self._panel.winfo_width()
        panel_h = self._panel.winfo_height()
        if panel_w < 40 or panel_h < 40:
            return
        if self._glass_active:
            self._resize_glass(panel_w, panel_h)
        else:
            self._resize_plain(panel_w, panel_h)

    def _text_req(self):
        """Height the two text lines ask for at their current fonts
        (plus the gap under the display).  Request sizes are valid
        before the window is mapped and, unlike actual sizes, do not
        follow the rows' stretching, so the tile height derived from
        them stays consistent with the grid at any window size."""
        return (self.formula_label.winfo_reqheight()
                + self.display_label.winfo_reqheight() + self._margin)

    def _target_bh(self, panel_h):
        """Tile height that makes the six button rows fit exactly below
        the two text lines (plus the gap under the display)."""
        return max(24, int((panel_h - self._text_req()) / 6.0)
                   - 2 * self._pad)

    def _apply_glass_size(self, bw, bh):
        """Apply one tile size: proportional corner radius and fonts,
        then the canvases of every button."""
        self._bw, self._bh = bw, bh
        # Everything that the base design ties to the tile height keeps
        # its ratio to it: corner radius and the three fonts.
        self._radius = max(
            2, int(round(bh * CORNER_RADIUS / float(BUTTON_HEIGHT))))
        font_button = (self._font_family,
                       -max(8, int(round(bh * 0.46))), u"bold")
        display_size = -max(14, int(round(bh * 0.80)))
        formula_size = -max(9, int(round(bh * 0.40)))
        self._display_base = display_size
        self._formula_base = formula_size
        self._display_font.configure(size=display_size)
        self._formula_font.configure(size=formula_size)
        # The labels get the same fonts at once: their requested
        # heights feed the next tile-height estimate of the settling
        # loop in _resize_glass, so they must already reflect the new
        # size when that estimate is taken.
        self.display_label.configure(
            font=(self._font_family, display_size, u"bold"))
        self.formula_label.configure(
            font=(self._font_family, formula_size, u"normal"))
        for key, buttons in self._key_buttons.items():
            span = key[1]
            width = bw * span + 2 * self._pad * (span - 1)
            for button in buttons:
                button.set_geometry(width, bh, font_button)
        self.root.update_idletasks()

    def _resize_glass(self, panel_w, panel_h):
        """Re-scale the glass layout to the panel size, keeping every
        element's relative position (proportional grid + proportional
        fonts, corner radius and tile sizes)."""
        # The panel is four equal uniform columns; a single-column tile
        # is a column minus pad on each side.  Tile height and the text
        # lines influence each other (fonts scale with the tile, the
        # lines with the fonts), so iterate until the height stabilizes;
        # a resize event recomputes from the same inputs, so repeated
        # passes settle on the very same size — no drift at the base
        # size and none afterwards.
        bw = max(24, int(panel_w / 4.0) - 2 * self._pad)
        bh = self._target_bh(panel_h)
        if bw == self._bw and bh == self._bh:
            return
        for _ in range(4):
            self._apply_glass_size(bw, bh)
            bh = self._target_bh(panel_h)
            if bh == self._bh:
                break
        self._refresh()
        # Rasterizing the tiles is the slow part (pure-Python pixel
        # math); redo it only once the size settled and moved far
        # enough from the rendered one.
        if (abs(bw - self._bw_rendered) >= 4
                or abs(bh - self._bh_rendered) >= 4):
            self._schedule_tile_rebuild()

    def _resize_plain(self, panel_w, panel_h):
        """Re-scale the plain layout: the grid stretches the buttons,
        the fonts follow the panel width proportionally."""
        if not self._plain_buttons or self._base_panel_w <= 0:
            return
        scale = float(panel_w) / float(self._base_panel_w)

        def scaled(base_size, lo, hi):
            value = int(round(base_size * scale))
            if value < lo:
                value = lo
            elif value > hi:
                value = hi
            return value

        sizes = (scaled(16, 10, 40), scaled(28, 16, 72),
                 scaled(14, 8, 36))
        if sizes == self._plain_sizes:
            return
        self._plain_sizes = sizes
        self._display_base = sizes[1]
        self._formula_base = sizes[2]
        self._display_font.configure(size=sizes[1])
        self._formula_font.configure(size=sizes[2])
        for button in self._plain_buttons:
            button.configure(font=(u"Consolas", sizes[0], u"bold"))
        self.root.update_idletasks()
        self._refresh()

    def _schedule_tile_rebuild(self):
        if self._rebuild_job is not None:
            try:
                self.root.after_cancel(self._rebuild_job)
            except tk.TclError:
                pass
        self._rebuild_job = self.root.after(200, self._start_tile_rebuild)

    def _start_tile_rebuild(self):
        self._rebuild_job = None
        if (abs(self._bw - self._bw_rendered) < 4
                and abs(self._bh - self._bh_rendered) < 4):
            return
        self._tile_generation += 1
        generation = self._tile_generation
        self._rebuild_queue = list(self._tile_key_order)
        self._drain_tile_rebuild(generation)

    def _drain_tile_rebuild(self, generation):
        """Re-render the tiles key by key; one key per event-loop tick
        keeps the window responsive while the pixel math runs."""
        if generation is not self._tile_generation:
            return  # a newer resize superseded this rebuild
        key = self._rebuild_queue.pop(0)
        self._render_key_photos(key)
        for button in self._key_buttons[key]:
            button.retile(self._key_photos[key])
        if self._rebuild_queue:
            self.root.after(0, lambda: self._drain_tile_rebuild(generation))
        else:
            self._bw_rendered = self._bw
            self._bh_rendered = self._bh

    def _render_key_photos(self, key):
        """Rasterize the cached scenes of one (kind, span) at the
        current tile size and replace that key's PhotoImages."""
        kind, span = key
        width = self._bw * span + 2 * self._pad * (span - 1)
        photos = {}
        for state, (alpha, sheen, brightness) in TILE_STATES.items():
            rows = tile_from_scene(self._scenes[(kind, span, state)],
                                   width, self._bh, self._radius,
                                   self._bg_rgb, alpha)
            photos[state] = self._make_photo(png_bytes(rows), ppm_bytes(rows))
        old = self._key_photos.get(key)
        self._key_photos[key] = photos
        if old is not None:
            # Python 2's Tkinter PhotoImage has no destroy(); dropping
            # the last references is enough there (refcounting frees
            # the Tcl image).  Callers retile the buttons in the same
            # tick, so no stale frame is ever drawn.
            for photo in old.values():
                destroy = getattr(photo, 'destroy', None)
                if destroy is not None:
                    try:
                        destroy()
                    except tk.TclError:
                        pass

    def _build_plain(self):
        bg = PALETTE["window"]
        self.root.configure(bg=bg)
        self._glass_active = False
        self._font_family = "Consolas"
        self._display_base = 28
        self._formula_base = 14
        self._display_font = tkfont.Font(self.root, family="Consolas",
                                         size=28, weight="bold")
        self._formula_font = tkfont.Font(self.root, family="Consolas",
                                         size=14)

        panel = tk.Frame(self.root, bg=bg, padx=10, pady=10)
        panel.pack(fill="both", expand=True)
        for col in range(4):
            panel.grid_columnconfigure(col, weight=1, uniform="button")
        for row in range(8):  # 2 text lines + 6 button rows
            panel.grid_rowconfigure(row, weight=1)
        self._panel = panel

        self.formula_var = tk.StringVar(value="")
        self._formula_box = self._make_text_box(panel, bg)
        self._formula_box.grid(row=0, column=0, columnspan=4, sticky="nsew")
        self.formula_label = tk.Label(self._formula_box,
                                      textvariable=self.formula_var,
                                      anchor="e",
                                      font=("Consolas", 14),
                                      fg=PALETTE["formula"], bg=bg)
        self.formula_label.pack(fill="both", expand=True)

        self.display_var = tk.StringVar(value="0")
        self._display_box = self._make_text_box(panel, bg)
        self._display_box.grid(row=1, column=0, columnspan=4,
                               sticky="nsew", pady=(0, 10))
        self.display_label = tk.Label(self._display_box,
                                      textvariable=self.display_var,
                                      anchor="e",
                                      font=("Consolas", 28, "bold"),
                                      fg=PALETTE["display"], bg=bg)
        self.display_label.pack(fill="both", expand=True)

        for text, kind, row, col, span in self.LAYOUT:
            fg, hover = PALETTE[kind]
            button = tk.Button(panel, text=text, width=4,
                               font=("Consolas", 16, "bold"),
                               command=lambda k=kind, t=text: self._handle(k, t),
                               bg=fg, activebackground=hover, fg="white",
                               relief="flat", bd=0,
                               highlightthickness=1, highlightbackground=PALETTE["border"],
                               cursor="hand2")
            button.grid(row=2 + row, column=col, columnspan=span,
                        sticky="nsew", padx=3, pady=3)
            self._plain_buttons.append(button)

        self.root.update_idletasks()
        self._base_panel_w = panel.winfo_reqwidth()

    # --- actions ---

    def _handle(self, kind, text):
        if kind == "digit":
            self.engine.press_digit(text)
        elif kind == "dot":
            self.engine.press_dot()
        elif kind == "operator":
            self.engine.press_operator(text)
        elif kind == "equals":
            self.engine.press_equals()
        elif kind == "backspace":
            self.engine.press_backspace()
        elif kind == "clear":
            self.engine.press_clear()
        self._refresh()

    def _refresh(self):
        self._fit_text(self.display_var, self.display_label,
                       self.engine.display_value(), self._display_base,
                       self._display_font, True)
        self._fit_text(self.formula_var, self.formula_label,
                       self.engine.formula_value(), self._formula_base,
                       self._formula_font, False)

    def _fit_text(self, var, label, text, base_size, font, bold):
        """Put text on the label; shrink the font if the text is wider
        than the label, so long error messages are never clipped."""
        var.set(text)
        weight = u"bold" if bold else u"normal"
        available = label.winfo_width()
        if available < 2:
            available = label.winfo_reqwidth()
        size = base_size
        if text and available > 0:
            needed = font.measure(text)
            if needed > available:
                size = int(base_size * (float(available) / needed))
                if abs(size) < 6:
                    size = -6 if base_size < 0 else 6
        label.configure(font=(self._font_family, size, weight))

    def _on_key(self, event):
        ch = event.char
        if ch in "0123456789":
            self._handle("digit", ch)
        elif ch in (".", ","):
            self._handle("dot", u".")
        elif ch in "+-*/":
            self._handle("operator", ch)
        elif ch == "^":
            self._handle("operator", u"pow")
        elif ch == "r":
            self._handle("operator", u"sqrt")
        elif ch == "=":
            self._handle("equals", u"=")
        elif event.keysym == "Return":
            self._handle("equals", u"=")
        elif event.keysym == "BackSpace":
            self._handle("backspace", u"←")
        elif event.keysym == "Escape":
            self._handle("clear", u"C")

    def start(self):
        self.root.bind("<Key>", self._on_key)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.update_idletasks()
        self._refresh()
        self.root.mainloop()

    def _on_close(self):
        # Invalidate any pending or in-flight resize/rebuild jobs so
        # their "after" callbacks die with the window.
        self._tile_generation += 1
        for job in (self._resize_job, self._rebuild_job):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        self.root.destroy()
        if self._glass_tmp is not None:
            shutil.rmtree(self._glass_tmp, ignore_errors=True)
            self._glass_tmp = None


def main():
    if HAS_CTK:
        root = ctk.CTk()
    else:
        root = tk.Tk()
    CalculatorApp(root).start()


if __name__ == "__main__":
    main()
