# AGENTS.md

## Primary Goal
The application is designed to perform basic operations and formula-based calculations. It features a user-friendly interface created using modern graphical technologies.

## Expected Repository Structure
- calculator/
- tests/
- .opencode/agents/
- .opencode/skills/
## Commands (run from repo root)

- All tests: `python -m unittest discover`
- One test: `python -m unittest tests.test_engine.EngineTests.test_sqrt`
- CLI: `python -m calculator`
- GUI: `python -m calculator.gui` (needs a display; not runnable headless)

## Environment / toolchain quirks

- Code must run on **both Python 2.7 and 3.x**, stdlib only: no f-strings or type hints; keep `from __future__ import division`, `u""` literals, `object` base classes.
- The local `python` is 2.7.18. Py2 `unittest` gotcha: flags go **before** the module — `python -m unittest -v tests.test_engine` works, `python -m unittest tests.test_engine -v` fails with `ImportError: No module named -v`.
- `str(float)` differs between Py2 (12 sig digits) and Py3 (shortest repr). Never assert exact float display strings in tests; use `float(...)` + `assertAlmostEqual`.
- Stale `.pyc` files sit next to every source file; ignore them, never edit them.

## GitHub remote safety

- Remote: `https://github.com/pinknyashka/calculator.git` (public). Push with `git push` (first run triggers Git Credential Manager browser login), or token-embedded: `git -c credential.helper= push "https://<TOKEN>@github.com/pinknyashka/calculator.git" main:main`.
- Creating branches, pushing commits, and opening PRs are allowed.
- NEVER delete on the remote without explicit user permission: no `git push --delete`, no `push :<branch>`, no force-push, no rewriting/deleting commits, no deleting the repository.

## Architecture

- `calculator/core.py` — pure functions: binary `OPERATORS` (`+ - * / pow`), unary `UNARY_OPERATORS` (`sqrt`); `calculate()` parses `"a op b"` or `"a sqrt"` / `"sqrt a"`. `core.pow` deliberately shadows the builtin.
- `calculator/engine.py` — `CalculatorEngine`, a GUI-free state machine (entry / operand / operator) driven by both CLI and GUI. Binary ops: `press_operator` + `press_equals` (which calls `calculate`). Unary ops are special-cased in `press_operator` (`sqrt` → `_apply_sqrt`), not in `OPERATORS`.
- `calculator/gui.py` — Tkinter UI; `CalculatorApp.LAYOUT` is the button grid, `_on_key` maps keyboard keys (`^` → `pow`, `r` → `sqrt`), `_handle` routes to the engine. `customtkinter` is optional — code must always fall back to plain Tkinter, and glass tiles fall back to a plain theme. The window is adaptive: resizable within `MIN_SCALE`..`MAX_SCALE` of the base size (`_enable_resizing`), panel `<Configure>` → `_on_resize` → `_apply_resize` re-scales geometry/fonts instantly; glass tiles are re-rendered on resize via cached unit scenes (`_schedule_tile_rebuild`/`_drain_tile_rebuild`, one key per tick). Both themes (glass and plain) must stay responsive.
- `calculator/glass.py` — pure-stdlib pixel math (PNG/PPM tiles); testable headless. `paint_scene` returns the size-independent unit scene (cache it); `tile_from_scene` rasterizes a cached scene at any size — this split is what makes resize re-rendering cheap. `render_tile` = scene + rasterize.

## Adding a new operator

Touch every layer or the feature silently breaks somewhere: core (function + `OPERATORS`/`UNARY_OPERATORS`), engine (unary ops need `_apply_sqrt`-style handling in `press_operator`), `gui.py` (`LAYOUT` + `_on_key`), `cli.py` help text, `__init__.py` exports, README, and tests in **both** `test_calculator.py` and `test_engine.py` (extend the `press_sequence` key map there, e.g. `^`/`r`).

## Test conventions

- `tests/test_calculator.py` = core, `test_engine.py` = state machine, `test_glass.py` = pixel math. No GUI tests (can't run headless).
- Engine user-facing error strings are Russian (`u"Ошибка: ..."`) and asserted verbatim in tests — add new errors in the same style and keep the exact strings in sync with tests.
