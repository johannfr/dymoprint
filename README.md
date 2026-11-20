# dymoprint

A command-line tool to print labels on a DYMO LetraTag 200B Bluetooth printer.

Give it a spacing (in millimeters) and a text file with one label per line.
It builds a single image containing every line, each centered so that
consecutive lines' text centers end up exactly that many millimeters apart,
and prints it as one continuous run of tape.

## Requirements

- A DYMO LetraTag 200B, powered on and in Bluetooth range.
- [Nix](https://nixos.org/) with flakes enabled.

## Running it

From a checkout of this repo:

```sh
nix run . -- 50 mytext.txt
```

For development (run straight from source, no install):

```sh
nix develop
python -m dymoprint.main 50 mytext.txt
```

## Usage

```
dymoprint [OPTIONS] SPACING_MM TEXT_FILE
```

- `SPACING_MM` — distance in millimeters between each label's text center
  and the next.
- `TEXT_FILE` — a plain text file, one label per line. Blank lines are
  skipped.

By default this searches for a printer over Bluetooth and prints
immediately. Pass `--preview` first if you just want to check the layout.

### Options

| Option | Description |
| --- | --- |
| `--font NAME` | Font family (see `--list-fonts`) or a path to a `.ttf`/`.otf` file. Default: `liberation-sans`. |
| `--font-size N` | Font size in pixels. The printable label height is a fixed 30px. Default: `20`. |
| `--bold` / `--italic` | Use the bold/italic variant of the chosen font. |
| `--list-fonts` | List the available font families and exit. |
| `--dither` / `--no-dither` | Floyd-Steinberg dithering when converting to monochrome. Default: on. |
| `--stretch N` | Stretch factor applied along the feed direction. Default: `2` (matches the DYMO app; otherwise labels print too thin). |
| `--feed-resolution N` | Calibration constant (pixels per mm) used to convert `SPACING_MM` to pixels. See [Calibration](#calibration). |
| `--timeout N` | Bluetooth discovery timeout in seconds. Default: `5`. |
| `--printer MAC` | Print to a specific printer by MAC address. Default: the first one found. |
| `--list-printers` | Scan for nearby printers, print what was found (name and MAC address), and exit. |
| `--preview` | Render the label to the terminal as text art instead of printing it. |

### Examples

List fonts:

```sh
dymoprint --list-fonts
```

See which printers are nearby:

```sh
dymoprint --list-printers
```

Preview a layout without printing:

```sh
dymoprint 50 mytext.txt --preview
```

Print in bold DejaVu Sans to a specific printer:

```sh
dymoprint 40 mytext.txt --font dejavu-sans --bold --printer AA:BB:CC:DD:EE:FF
```

## Calibration

`--feed-resolution` controls how many millimeters of tape a given spacing
actually consumes. The shipped default was measured from real test prints,
but printer units may vary slightly. To check yours: print a known spacing,
measure the actual distance between label centers with a ruler, then scale
the current value:

```
new_value = current_value * (intended_mm / actual_mm)
```

Pass the result as `--feed-resolution <new_value>` on future runs.
