# calculator

A small Python calculator with the four basic operations (`+`, `-`, `*`, `/`),
exponentiation (`pow`) and square root (`sqrt`).
Console CLI and a Tkinter GUI. Works on Python 2.7 and Python 3.x,
standard library only (the GUI needs a Python built with Tk, as in the
python.org installers). The GUI optionally uses `customtkinter` for a
modern "glass" look — see the [GUI](#gui) section.

## Layout

```
calculator/
├── calculator/
│   ├── core.py          # add, subtract, multiply, divide, pow, sqrt, calculate()
│   ├── engine.py        # CalculatorEngine: pure state machine (testable, no GUI)
│   ├── cli.py           # console REPL
│   ├── glass.py         # Gaussian-smoothed glass tile textures (pure stdlib)
│   ├── gui.py           # Tkinter window (buttons + display)
│   └── __main__.py      # enables `python -m calculator`
└── tests/
    ├── test_calculator.py
    ├── test_engine.py
    └── test_glass.py
```

## GUI

```
python -m calculator.gui
```

Buttons are drawn as **frosted-glass tiles**: at start-up each tile is
computed by `calculator/glass.py` (pure standard library, no PIL) from a
color gradient plus **Gaussian-smoothed** texture — white noise blurred
with a separable 2-D Gaussian kernel (the "frosted" grain), a
Gaussian-smoothed specular sheen near the top edge, and a soft bevel.
Each button pre-renders *normal*, *hover* and *pressed* tile variants.

- On Tcl/Tk 8.6+ (Python 3) the tiles are PNGs with per-pixel alpha, so
  the rounded corners stay smooth and the panel shows through;
- on older Tk (Python 2.7 ships 8.5) the same tiles are written as PPM
  images pre-composited against the window background color, so the
  glass look works there too — the effect is available with or without
  [`customtkinter`](https://github.com/TomSchimansky/CustomTkinter)
  (which, if installed, still provides the root window and the
  translucent window on Windows);
- if anything is unavailable the GUI falls back to a plain dark
  Tkinter theme (standard library only, works on Python 2.7).

The window is **adaptive**: it can be resized within a limited range
(80%–150% of the default size, see `MIN_SCALE`/`MAX_SCALE` in
`gui.py`) and every element follows while keeping its relative
position — buttons stretch proportionally, the display and formula
lines grow with the window, and all fonts scale with the tile size.
In the glass theme the tiles are re-rendered on resize: the
size-independent scene is cached at start-up
(`calculator.glass.paint_scene`), so only the final rasterization is
redone (`calculator.glass.tile_from_scene`), which keeps resizing
responsive.

- digit and `.` buttons enter the current number (shown on the main display);
- `+ - * / pow` pick the operation (the pending "a op" appears on the formula line);
- `sqrt` is unary: it applies to the number currently entered (or the result
  shown) and displays it immediately, e.g. `9` → `sqrt` → `3`;
- `=` shows the full formula with the total, e.g. `3 + 4 = 7`;
- `C` clears, `←` deletes the last digit;
- the same keys work from the keyboard: `0-9 . + - * / ^ r = Enter Backspace Esc`
  (`^` is the `pow` operator, `r` is `sqrt`).

## Console CLI

```
> python -m calculator
>>> 3 + 4
7
>>> quit
```

## As a library

```python
from calculator import add, subtract, multiply, divide, pow, sqrt, calculate, CalculatorEngine

add(2, 3)            # 5
divide(7, 2)         # 3.5
pow(2, 10)           # 1024
sqrt(9)              # 3.0
calculate("10 - 4")  # 6
calculate("2 pow 3") # 8
calculate("9 sqrt")  # 3
```

## Tests

```
python -m unittest discover
```
