"""mm<->px math and composite label image construction.

See CLAUDE.md ("Hardware facts") for where these constants come from.
"""

import sys
from typing import Sequence

from dymo_bluetooth import Canvas
from PIL import Image, ImageDraw, ImageFont

LABEL_HEIGHT_PX = Canvas.FIXED_EDGE_PIXELS  # 30px, fixed by the printhead

# Pixels-per-mm of the *actual printed output*, along the feed/length axis,
# independent of --stretch (stretch just resends each column N times; it
# doesn't change the physical size of a column once printed).
#
# This is NOT derived from the printhead spec (30px over a 12mm tape, i.e.
# 2.5 px/mm) -- that ratio only describes the cross-axis print head, and
# turned out not to carry over to the feed axis. Calibrated from two real
# test prints instead:
#   1. 45mm requested -> ~18mm actual, giving an initial estimate of
#      (45mm * 2.5px/mm * 2) / 18mm = 12.5 px/mm.
#   2. At that value, 50mm requested -> 50.5mm actual (close, but 0.5mm
#      long), giving a corrected 12.5 * (50mm / 50.5mm) = 12.376 px/mm.
# Still a field calibration, not a datasheet figure -- if your own print is
# still off, pass --feed-resolution <this_value * intended_mm / actual_mm>.
NATIVE_FEED_PX_PER_MM = 12.376

MAX_CANVAS_WIDTH_PX = Canvas.UNFIXED_EDGE_MAX_PIXELS  # 8000px, enforced again after stretch()


def mm_to_px(mm: float, stretch: int, feed_px_per_mm: float = NATIVE_FEED_PX_PER_MM) -> int:
    """Pre-stretch pixel count needed so that, once stretched, `mm` of tape
    is actually consumed."""
    return round(mm * feed_px_per_mm / stretch)


def build_composite_image(
    lines: Sequence[str],
    spacing_mm: float,
    font: ImageFont.FreeTypeFont,
    stretch: int,
    feed_px_per_mm: float = NATIVE_FEED_PX_PER_MM,
) -> Image.Image:
    """Build one wide 1-bit image containing every line, each centered in a
    slot `spacing_mm` wide, so consecutive lines' text centers are exactly
    `spacing_mm` apart once printed."""
    slot_px = mm_to_px(spacing_mm, stretch, feed_px_per_mm)
    if slot_px <= 0:
        raise ValueError("Spacing is too small to produce any pixels at this resolution.")

    total_width = slot_px * len(lines)
    max_pre_stretch_width = MAX_CANVAS_WIDTH_PX // stretch
    if total_width > max_pre_stretch_width:
        max_mm = max_pre_stretch_width * stretch / feed_px_per_mm
        raise ValueError(
            f"Layout would be {total_width}px wide before stretching, but the printer "
            f"accepts at most {max_pre_stretch_width}px at --stretch {stretch} "
            f"(~{max_mm:.0f}mm total). Reduce spacing/line count, or lower --stretch."
        )

    image = Image.new("1", (total_width, LABEL_HEIGHT_PX), color=1)  # white background
    draw = ImageDraw.Draw(image)

    for i, text in enumerate(lines):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        if text_h > LABEL_HEIGHT_PX:
            print(
                f"warning: '{text}' renders {text_h}px tall, taller than the "
                f"{LABEL_HEIGHT_PX}px printable height, and will be cropped. "
                "Try a smaller --font-size.",
                file=sys.stderr,
            )
        if text_w > slot_px:
            print(
                f"warning: '{text}' renders {text_w}px wide, wider than its "
                f"{slot_px}px slot, and may overlap neighboring text.",
                file=sys.stderr,
            )

        slot_center_x = (i + 0.5) * slot_px
        x = round(slot_center_x - text_w / 2 - bbox[0])
        y = round((LABEL_HEIGHT_PX - text_h) / 2 - bbox[1])
        draw.text((x, y), text, font=font, fill=0)  # black text

    return image
