# dymoprint

A Python CLI that prints labels onto a DYMO LetraTag 200B Bluetooth printer.
Given a spacing in millimeters and a text file (one label string per line),
it builds a single wide monochrome image containing every line, each
center-aligned within its own slot, so consecutive labels' text centers end
up exactly `spacing` mm apart on one continuous tape run — then sends it as
one Bluetooth print job.

## Workflow / environment notes

- I (the user) handle all git operations manually. Do not run `git init`,
  `git add`, `git commit`, etc. unless I explicitly ask.
- Nix/nixpkgs: use the **nixos-26.05** stable channel (not unstable). I'll
  tell you when I've upgraded to a newer stable and want the flake bumped.
- No `pyproject.toml` or `requirements.txt` — `flake.nix` is the only
  packaging/dependency manifest for this project, by design.

## Project layout

```
flake.nix           - Nix flake: devShell + package + app
dymoprint/
  __init__.py
  fonts.py           - curated font registry (see "Fonts" below)
  layout.py          - mm<->px math, builds the composite PIL image
  printing.py        - PIL Image -> dymo_bluetooth Canvas, BLE discovery/print
  main.py            - Click CLI entry point (`python -m dymoprint.main`)
```

## Hardware facts (from dymo-bluetooth's source/docs, not guesses)

- `dymo_bluetooth.Canvas.FIXED_EDGE_PIXELS` = 30 px, documented as 12mm of
  label height → 2.5 px/mm **cross-axis** (printhead element pitch). This
  is still used as-is for `LABEL_HEIGHT_PX`, the fixed vertical pixel
  budget for the composite image.
- The feed/length axis (used for `SPACING_MM`) is a **different, unrelated
  physical pitch** — we originally assumed it shared the cross-axis's 2.5
  px/mm (to keep the drawn image internally square before `stretch()`), but
  real test prints proved that wrong, and have been used to calibrate
  `NATIVE_FEED_PX_PER_MM` (`layout.py`) twice so far:
  1. 45mm requested → ~18mm actual → first estimate 12.5 px/mm.
  2. 50mm requested (at 12.5 px/mm) → 50.5mm actual (0.5mm long) →
     corrected to `12.5 * (50/50.5) ≈ 12.376` px/mm, the current default.
  Used as `spacing_mm * 12.376 / stretch` to get the pre-stretch slot width
  in pixels. Still a field calibration, not a datasheet number —
  `--feed-resolution` overrides it if another test print is still off
  (scale the current value by `intended_mm / actual_mm`).
- Per `dymo_bluetooth`'s own README/CLI, the vendor app also **stretches by
  2x** along the feed axis before sending to the printer, or labels print
  "too thin" — we replicate that via `Canvas.stretch(2)` (default
  `--stretch 2`, overridable). Stretch is stretch-axis pixel duplication,
  not a resolution change, so `NATIVE_FEED_PX_PER_MM` is defined as
  stretch-independent (the physical size of one printed pixel), and we
  divide by `--stretch` when converting mm to pre-stretch pixels.
- `Canvas.UNFIXED_EDGE_MAX_PIXELS` = 8000 px is enforced on both the
  pre-stretch and the post-stretch canvas (stretch() re-validates bounds).
  So the real ceiling on our composite image width is `8000 / stretch`
  pixels. `layout.py` checks this up front with a friendly error instead of
  letting `Canvas.set_pixel` raise deep inside `stretch()`.

## Packaging decisions (flake.nix)

- `dymo-bluetooth` isn't in nixpkgs; it's pulled directly from its PyPI
  wheel via `fetchurl` + `buildPythonPackage` (format = "wheel"), pinned to
  **0.1.3**.
- It declares `bleak~=1.1.1`, but nixpkgs 26.05 ships bleak 2.1.1 — a major
  version jump for a BLE library is too risky to relax silently, so we
  vendor our **own pinned `bleak` 1.1.1** the same way (wheel + fetchurl),
  rather than using nixpkgs' bleak. Verified this combination actually
  imports and that `Canvas`/`stretch()` work via a scratch build.
- It also declares `pillow~=11.0.0`; nixpkgs 26.05 ships Pillow 13.0.0. This
  one we *do* relax (`pythonRelaxDeps = [ "pillow" ]`), since the only
  Pillow APIs `dymo_bluetooth` touches (`Image.convert("1")`, `ImageChops`,
  `crop`, `getpixel`) are long-stable basics, unlike a BLE transport layer.
- Fonts are a curated bundle (`liberation_ttf` + `dejavu_fonts` from
  nixpkgs), not a system fontconfig scan — see below.
- The wrapper runs `python -P -m dymoprint.main`. The `-P` matters: `-m`
  normally prepends the current working directory to `sys.path`, so without
  it, running the built `dymoprint` binary (or `nix run .`) from inside a
  checkout of *this* repo would let the raw, unsubstituted `./dymoprint/`
  source shadow the installed copy — reproducing the `@liberation_ttf@`
  placeholder bug. Found this by literally hitting it via the README's own
  `nix run .` example.

## Fonts

- Default font family: **Liberation Sans** (metrically compatible with
  Arial, which isn't freely licensed / isn't in nixpkgs).
- `fonts.py` holds a small registry of family → {regular, bold, italic,
  bold-italic} → filename, for `liberation-{sans,serif,mono}` and
  `dejavu-{sans,serif,mono}`. `--list-fonts` enumerates exactly this
  registry — nothing from the host system.
- The registry's directory placeholders (`@liberation_ttf@`, `@dejavu_fonts@`)
  are substituted with real Nix store paths at build time (see `postPatch`
  in flake.nix). For `nix develop`, the dev shell instead sets
  `DYMOPRINT_LIBERATION_DIR` / `DYMOPRINT_DEJAVU_DIR` env vars, which
  `fonts.py` prefers when present.
- `--font` also accepts an absolute path to any `.ttf`/`.otf` file (e.g. a
  real Arial file you happen to have), bypassing the registry entirely.

## CLI behavior

- Default action is to actually search for the printer over Bluetooth and
  print — matches the example invocation in the original spec
  (`python -m dymoprint.main 50 mytext.txt`). `--preview` renders the
  composite label to the terminal (via `Canvas.text()`) without touching
  Bluetooth, for testing without hardware.
- Blank lines in the input text file are silently dropped.
- `SPACING_MM`/`TEXT_FILE` are positional but not strictly required at the
  Click level (`required=False, default=None`) so that `--list-printers`
  can run standalone; the body raises a `UsageError` itself if they're
  missing and `--list-printers` wasn't given.
- `--list-printers` scans and prints `name (MAC)` for each discovered
  printer, then exits without building/printing anything.
- `--printer MAC` selects which discovered printer to print to (case-
  insensitive match against the BLE device address); omitted means "first
  one found", matching upstream's own CLI behavior.
- `Printer` doesn't expose its MAC/name publicly — `printing.py` reaches
  into `printer._impl.address`/`.name` (the underlying bleak device), same
  as `dymo_bluetooth`'s own `__main__.py` does.
