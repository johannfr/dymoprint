"""Curated font registry.

The directory placeholders below are substituted with real Nix store paths
at build time (see `postPatch` in flake.nix). Under `nix develop`, the dev
shell instead sets DYMOPRINT_LIBERATION_DIR / DYMOPRINT_DEJAVU_DIR, which
take priority over the placeholders.
"""

import os
from pathlib import Path
from typing import Dict

_LIBERATION_DIR = os.environ.get("DYMOPRINT_LIBERATION_DIR", "@liberation_ttf@")
_DEJAVU_DIR = os.environ.get("DYMOPRINT_DEJAVU_DIR", "@dejavu_fonts@")

STYLES = ("regular", "bold", "italic", "bold-italic")

FONT_FAMILIES: Dict[str, Dict[str, str]] = {
    "liberation-sans": {
        "dir": _LIBERATION_DIR,
        "regular": "LiberationSans-Regular.ttf",
        "bold": "LiberationSans-Bold.ttf",
        "italic": "LiberationSans-Italic.ttf",
        "bold-italic": "LiberationSans-BoldItalic.ttf",
    },
    "liberation-serif": {
        "dir": _LIBERATION_DIR,
        "regular": "LiberationSerif-Regular.ttf",
        "bold": "LiberationSerif-Bold.ttf",
        "italic": "LiberationSerif-Italic.ttf",
        "bold-italic": "LiberationSerif-BoldItalic.ttf",
    },
    "liberation-mono": {
        "dir": _LIBERATION_DIR,
        "regular": "LiberationMono-Regular.ttf",
        "bold": "LiberationMono-Bold.ttf",
        "italic": "LiberationMono-Italic.ttf",
        "bold-italic": "LiberationMono-BoldItalic.ttf",
    },
    "dejavu-sans": {
        "dir": _DEJAVU_DIR,
        "regular": "DejaVuSans.ttf",
        "bold": "DejaVuSans-Bold.ttf",
        "italic": "DejaVuSans-Oblique.ttf",
        "bold-italic": "DejaVuSans-BoldOblique.ttf",
    },
    "dejavu-serif": {
        "dir": _DEJAVU_DIR,
        "regular": "DejaVuSerif.ttf",
        "bold": "DejaVuSerif-Bold.ttf",
        "italic": "DejaVuSerif-Italic.ttf",
        "bold-italic": "DejaVuSerif-BoldItalic.ttf",
    },
    "dejavu-mono": {
        "dir": _DEJAVU_DIR,
        "regular": "DejaVuSansMono.ttf",
        "bold": "DejaVuSansMono-Bold.ttf",
        "italic": "DejaVuSansMono-Oblique.ttf",
        "bold-italic": "DejaVuSansMono-BoldOblique.ttf",
    },
}

DEFAULT_FONT_FAMILY = "liberation-sans"


def style_key(bold: bool, italic: bool) -> str:
    if bold and italic:
        return "bold-italic"
    if bold:
        return "bold"
    if italic:
        return "italic"
    return "regular"


def resolve_font(name: str, bold: bool, italic: bool) -> Path:
    """Resolve a font family name (from FONT_FAMILIES) or a direct path to a
    .ttf/.otf file into a concrete font file path."""
    direct = Path(name)
    if direct.suffix.lower() in (".ttf", ".otf"):
        if not direct.is_file():
            raise ValueError(f"Font file '{direct}' does not exist.")
        return direct

    family = FONT_FAMILIES.get(name)
    if family is None:
        known = ", ".join(sorted(FONT_FAMILIES))
        raise ValueError(
            f"Unknown font '{name}'. Known fonts: {known}. "
            "Run --list-fonts to see styles, or pass a path to a .ttf/.otf file."
        )
    filename = family[style_key(bold, italic)]
    return Path(family["dir"]) / "share" / "fonts" / "truetype" / filename


def list_fonts():
    """Yield one human-readable line per known font family."""
    for name, family in sorted(FONT_FAMILIES.items()):
        styles = [s for s in STYLES if s in family]
        yield f"{name} ({', '.join(styles)})"
