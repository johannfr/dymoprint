import asyncio
from pathlib import Path
from typing import Optional

import click
from PIL import ImageFont

from . import fonts, layout
from .printing import discover, print_canvas, printer_label, render_canvas


def _list_fonts_and_exit(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    for line in fonts.list_fonts():
        click.echo(line)
    ctx.exit()


@click.command()
@click.argument("spacing_mm", type=float, required=False, default=None)
@click.argument(
    "text_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    default=None,
)
@click.option(
    "--font",
    default=fonts.DEFAULT_FONT_FAMILY,
    show_default=True,
    help="Font family name (see --list-fonts) or a path to a .ttf/.otf file.",
)
@click.option(
    "--font-size",
    default=20,
    show_default=True,
    type=int,
    help="Font size in pixels. The printable label height is fixed at 30px.",
)
@click.option("--bold", is_flag=True, default=False, help="Use the bold variant of the font.")
@click.option("--italic", is_flag=True, default=False, help="Use the italic variant of the font.")
@click.option(
    "--list-fonts",
    is_flag=True,
    callback=_list_fonts_and_exit,
    expose_value=False,
    is_eager=True,
    help="List available font families and exit.",
)
@click.option(
    "--dither/--no-dither",
    default=True,
    show_default=True,
    help="Use Floyd-Steinberg dithering when converting to monochrome.",
)
@click.option(
    "--stretch",
    default=2,
    show_default=True,
    type=int,
    help="Stretch factor along the feed direction (the vendor app uses 2; "
    "otherwise labels print too thin).",
)
@click.option(
    "--feed-resolution",
    default=layout.NATIVE_FEED_PX_PER_MM,
    show_default=True,
    type=float,
    help="Printed pixels-per-mm along the feed direction, used to convert "
    "SPACING_MM to pixels. Back-calculated from test prints, so it may "
    "still be off for your unit -- if a test print's spacing is wrong by "
    "some factor, multiply this value by (intended_mm / actual_mm) and retry.",
)
@click.option(
    "--timeout",
    default=5,
    show_default=True,
    type=int,
    help="Bluetooth discovery timeout in seconds.",
)
@click.option(
    "--printer",
    "mac_address",
    default=None,
    help="MAC address of the printer to use. Defaults to the first printer found.",
)
@click.option(
    "--list-printers",
    is_flag=True,
    default=False,
    help="Scan for nearby printers, print what was found, and exit without printing anything.",
)
@click.option(
    "--preview",
    is_flag=True,
    default=False,
    help="Render the label layout to the terminal instead of printing it.",
)
def cli(
    spacing_mm: Optional[float],
    text_file: Optional[Path],
    font,
    font_size,
    bold,
    italic,
    dither,
    stretch,
    feed_resolution,
    timeout,
    mac_address: Optional[str],
    list_printers,
    preview,
):
    """Print each line of TEXT_FILE as a center-aligned label on a DYMO
    LetraTag 200B, with consecutive lines' text centers spaced SPACING_MM
    millimeters apart on one continuous tape run."""
    if list_printers:
        click.echo(f"Scanning for printers (timeout {timeout}s)...", err=True)
        printers = asyncio.run(discover(timeout))
        if not printers:
            click.echo("No printers found.", err=True)
            return
        for printer in printers:
            click.echo(printer_label(printer))
        return

    if spacing_mm is None or text_file is None:
        raise click.UsageError("SPACING_MM and TEXT_FILE are required unless --list-printers is given.")
    if spacing_mm <= 0:
        raise click.UsageError("SPACING_MM must be greater than 0.")
    if stretch < 1:
        raise click.UsageError("--stretch must be at least 1.")

    lines = [line.strip() for line in text_file.read_text().splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise click.UsageError(f"{text_file} contains no non-empty lines.")

    try:
        font_path = fonts.resolve_font(font, bold, italic)
    except ValueError as e:
        raise click.UsageError(str(e))

    try:
        pil_font = ImageFont.truetype(str(font_path), font_size)
    except OSError as e:
        raise click.UsageError(f"Could not load font '{font_path}': {e}")

    try:
        image = layout.build_composite_image(
            lines, spacing_mm, pil_font, stretch, feed_resolution
        )
    except ValueError as e:
        raise click.UsageError(str(e))

    canvas = render_canvas(image, dither, stretch)

    if preview:
        click.echo(f"Label size: {canvas.size[0]}x{canvas.size[1]} px", err=True)
        click.echo(canvas.text())
        return

    click.echo(f"Searching for a printer (timeout {timeout}s)...", err=True)
    try:
        result = asyncio.run(print_canvas(canvas, timeout, mac_address))
    except RuntimeError as e:
        raise click.ClickException(str(e))
    click.echo(f"Result: {result.name}", err=True)


if __name__ == "__main__":
    cli()
