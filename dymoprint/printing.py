"""PIL Image -> dymo_bluetooth Canvas, and the Bluetooth discover/print flow."""

from typing import List, Optional

from dymo_bluetooth import Canvas, Result, convert_image_to_canvas, discover_printers
from dymo_bluetooth.bluetooth import Printer  # not re-exported from dymo_bluetooth's top-level __init__
from PIL import Image


def render_canvas(image: Image.Image, dither: bool, stretch: int) -> Canvas:
    canvas = convert_image_to_canvas(image, dither=dither)
    if stretch != 1:
        canvas = canvas.stretch(stretch)
    return canvas


def printer_label(printer: Printer) -> str:
    # Printer only exposes the underlying bleak device via a private
    # attribute; dymo_bluetooth's own __main__.py does the same thing.
    device = printer._impl
    return f"{device.name} ({device.address})"


async def discover(timeout: int) -> List[Printer]:
    return await discover_printers(timeout)


async def find_printer(timeout: int, mac_address: Optional[str] = None) -> Printer:
    printers = await discover(timeout)
    if not printers:
        raise RuntimeError(
            "No printer found. Make sure the DYMO LetraTag 200B is powered on and in range."
        )
    if mac_address is None:
        return printers[0]
    normalized = mac_address.strip().lower()
    for printer in printers:
        if printer._impl.address.lower() == normalized:
            return printer
    found = ", ".join(printer_label(p) for p in printers)
    raise RuntimeError(f"No printer with MAC address '{mac_address}' found nearby. Found: {found}")


async def print_canvas(canvas: Canvas, timeout: int, mac_address: Optional[str] = None) -> Result:
    printer = await find_printer(timeout, mac_address)
    await printer.connect()
    try:
        return await printer.print(canvas)
    finally:
        await printer.disconnect()
