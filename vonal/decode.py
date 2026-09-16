"""PNG -> Plate, by exact template lookup. Nothing here is statistical."""

from __future__ import annotations

from PIL import Image

from vonal import isa, palette, render
from vonal.cell import Cell, Form, Plate
from vonal.errors import LoadError


def _colours(block: Image.Image, x: int, y: int) -> list[tuple[int, int, int]]:
    counted = block.getcolors(maxcolors=render.CELL * render.CELL)
    found = [colour for _, colour in counted]
    for colour in found:
        if palette.index_of(colour) is None:
            raise LoadError(x, y, f"colour {colour} is not in the palette")
    if len(found) > 2:
        raise LoadError(x, y, f"a cell shows at most two colours, found {len(found)}")
    return found


def _decode_cell(block: Image.Image, x: int, y: int) -> Cell:
    found = _colours(block, x, y)
    # extent(7) is 50 < 64, so a corner pixel is always ground.
    ground_rgb = block.getpixel((0, 0))
    ground = palette.index_of(ground_rgb)

    if len(found) == 1:
        return Cell(Form.VOID, 0, 0, ground)

    form_rgb = next(colour for colour in found if colour != ground_rgb)
    variant = palette.index_of(form_rgb)

    mask = bytes(
        render.FORM if pixel == form_rgb else render.GROUND for pixel in block.getdata()
    )
    match = render.TEMPLATES.get(mask)
    if match is None:
        raise LoadError(x, y, "no glyph matches this cell")
    form, scale = match

    if isa.lookup(form, variant) is None:
        raise LoadError(x, y, f"undefined instruction: {form.name} variant {variant}")
    return Cell(form, variant, scale, ground)


def decode(image: Image.Image) -> Plate:
    """Read a plate image back into a Plate, or raise LoadError naming the cell."""
    image = image.convert("RGB")
    width, height = image.size
    if not width or not height or width % render.CELL or height % render.CELL:
        raise LoadError(0, 0, f"image dimensions {width}x{height} are not a multiple of 64")

    cols, rows = width // render.CELL, height // render.CELL
    grid = tuple(
        tuple(
            _decode_cell(
                image.crop((
                    x * render.CELL,
                    y * render.CELL,
                    (x + 1) * render.CELL,
                    (y + 1) * render.CELL,
                )),
                x,
                y,
            )
            for x in range(cols)
        )
        for y in range(rows)
    )
    return Plate(cols, rows, grid)
