"""Plate -> PNG, and the glyph templates the decoder recognises cells by.

This module is the single source of truth for what a glyph looks like. The
decoder holds no shape-recognition code; it looks up the templates produced
here, so the two cannot drift apart.
"""

from __future__ import annotations

import functools

from PIL import Image, ImageDraw

from vonal import palette
from vonal.cell import Cell, Form, Plate

CELL = 64

# Mask values. FORM is 255 because the mask is used directly as a Pillow paste
# mask, where the value is alpha.
GROUND = 0
FORM = 255


def extent(scale: int) -> int:
    """Side of the square a form is inscribed in, for scale 0..7.

    The top of the range leaves a 3 pixel margin, which is as close to filling
    the cell as the decoder allows: it reads the ground from the corner pixel,
    so a figure must never reach one.
    """
    return 8 + 7 * scale


def _box(scale: int) -> tuple[int, int, int, int]:
    length = extent(scale)
    offset = (CELL - length) // 2
    return offset, offset, offset + length - 1, offset + length - 1


def _draw(draw: ImageDraw.ImageDraw, form: Form, scale: int) -> None:
    left, top, right, bottom = _box(scale)
    length = extent(scale)
    mid_x = (left + right) // 2
    mid_y = (top + bottom) // 2

    if form is Form.DISC:
        draw.ellipse((left, top, right, bottom), fill=FORM)
    elif form is Form.SQUARE:
        draw.rectangle((left, top, right, bottom), fill=FORM)
    elif form is Form.RHOMBUS:
        draw.polygon([(mid_x, top), (right, mid_y), (mid_x, bottom), (left, mid_y)], fill=FORM)
    elif form is Form.TRIANGLE_N:
        draw.polygon([(mid_x, top), (right, bottom), (left, bottom)], fill=FORM)
    elif form is Form.TRIANGLE_S:
        draw.polygon([(mid_x, bottom), (right, top), (left, top)], fill=FORM)
    elif form is Form.TRIANGLE_E:
        draw.polygon([(right, mid_y), (left, top), (left, bottom)], fill=FORM)
    elif form is Form.TRIANGLE_W:
        draw.polygon([(left, mid_y), (right, top), (right, bottom)], fill=FORM)
    elif form is Form.HALF_DISC:
        # Flat side down: the upper half of the ellipse. Pillow measures angles
        # from 3 o'clock, clockwise, with y increasing downward.
        draw.pieslice((left, top, right, bottom), 180, 360, fill=FORM)
    elif form is Form.RING:
        thickness = max(2, length // 4)
        draw.ellipse((left, top, right, bottom), fill=FORM)
        draw.ellipse(
            (left + thickness, top + thickness, right - thickness, bottom - thickness),
            fill=GROUND,
        )
    elif form is Form.CROSS:
        thickness = max(2, length // 3)
        half = thickness // 2
        draw.rectangle((left, mid_y - half, right, mid_y - half + thickness - 1), fill=FORM)
        draw.rectangle((mid_x - half, top, mid_x - half + thickness - 1, bottom), fill=FORM)
    else:  # pragma: no cover - VOID never reaches here
        raise ValueError(f"{form} has no glyph")


@functools.cache
def template(form: Form, scale: int) -> bytes:
    """A CELL*CELL mask: GROUND where the ground shows, FORM where the glyph does."""
    image = Image.new("L", (CELL, CELL), GROUND)
    _draw(ImageDraw.Draw(image), form, scale)
    return image.tobytes()


def _build_templates() -> dict[bytes, tuple[Form, int]]:
    table: dict[bytes, tuple[Form, int]] = {}
    for form in Form:
        if form is Form.VOID:
            continue  # renders identically at every scale; found by the one-colour test
        for scale in range(8):
            mask = template(form, scale)
            if mask in table:
                raise AssertionError(
                    f"{form.name}@{scale} renders identically to "
                    f"{table[mask][0].name}@{table[mask][1]}; glyphs must be distinguishable"
                )
            table[mask] = (form, scale)
    return table


TEMPLATES: dict[bytes, tuple[Form, int]] = _build_templates()


def _cell_image(cell: Cell) -> Image.Image:
    block = Image.new("RGB", (CELL, CELL), palette.rgb(cell.ground))
    if cell.is_void:
        return block
    mask = Image.frombytes("L", (CELL, CELL), template(cell.form, cell.scale))
    block.paste(Image.new("RGB", (CELL, CELL), palette.rgb(cell.figure)), (0, 0), mask)
    return block


def paint(image: Image.Image, x: int, y: int, cell: Cell) -> None:
    """Draw one cell into a rendered plate, in place."""
    image.paste(_cell_image(cell), (x * CELL, y * CELL))


# The eye marker is two one-pixel lines, cream outside black, so one of them
# contrasts with any ground. Both lie in the cell's outer MARK_WIDTH pixels,
# which no glyph reaches (see extent), so marking never hides what a cell is.
MARK_WIDTH = 2
_MARK_COLOURS = (palette.rgb(1), palette.rgb(0))


def mark(image: Image.Image, x: int, y: int) -> None:
    """Outline cell (x, y) in place, to show where the eye stands.

    A marked image is a picture of the machine, not of the plate: its corner
    pixels are no longer ground, so it does not decode.
    """
    draw = ImageDraw.Draw(image)
    left, top = x * CELL, y * CELL
    for inset, colour in enumerate(_MARK_COLOURS):
        draw.rectangle(
            (left + inset, top + inset, left + CELL - 1 - inset, top + CELL - 1 - inset),
            outline=colour,
        )


def render(plate: Plate) -> Image.Image:
    """Render a Plate as a hard-edged RGB image."""
    image = Image.new("RGB", (plate.width * CELL, plate.height * CELL))
    for y, row in enumerate(plate.cells):
        for x, cell in enumerate(row):
            paint(image, x, y, cell)
    return image
