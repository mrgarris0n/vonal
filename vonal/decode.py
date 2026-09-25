"""PNG -> Plate, by exact template lookup. Nothing here is statistical."""

from __future__ import annotations

import os
import threading
from typing import cast

from PIL import Image, ImageChops

from vonal import isa, palette, render
from vonal.cell import Cell, Form, Plate
from vonal.errors import LoadError, VonalError

# A cell is 64 by 64 pixels, so a real program is a legitimately enormous
# image: a 170x165 plate is 115 megapixels, well past Pillow's 89 megapixel
# decompression-bomb threshold. Vonal compiled that plate itself, and loading
# it back printed a DecompressionBombWarning over correct output. The guard is
# still worth having, since a small PNG that inflates to gigabytes is a real
# attack and a plate is not always one you wrote, so it is raised rather than
# switched off. 256x256 cells is the ceiling: 16384 pixels square, about 800MB
# once decoded to RGB, which is the practical limit anyway.
MAX_CELLS = 256 * 256
MAX_PIXELS = MAX_CELLS * render.CELL * render.CELL


# A bytes.translate() table: 0 stays GROUND, any other value becomes FORM.
_NONZERO = bytes([render.GROUND] + [render.FORM] * 255)


def _colours(block: Image.Image, x: int, y: int) -> dict[palette.RGB, int]:
    """The cell's colours, each with its palette index. Any other colour is an error."""
    counted = block.getcolors(maxcolors=render.CELL * render.CELL)
    if counted is None:
        raise AssertionError("a cell cannot hold more colours than it has pixels")
    found: dict[palette.RGB, int] = {}
    for _, colour in counted:
        rgb = cast(palette.RGB, colour)  # decode() converted the image to RGB
        index = palette.index_of(rgb)
        if index is None:
            raise LoadError(x, y, f"colour {rgb} is not in the palette")
        found[rgb] = index
    if len(found) > 2:
        raise LoadError(x, y, f"a cell shows at most two colours, found {len(found)}")
    return found


def _decode_cell(block: Image.Image, x: int, y: int) -> Cell:
    found = _colours(block, x, y)
    # extent(7) is 50 < 64, so a corner pixel is always ground.
    ground_rgb = cast(palette.RGB, block.getpixel((0, 0)))
    ground = found[ground_rgb]

    if len(found) == 1:
        return Cell(Form.VOID, 0, 0, ground)

    form_rgb = next(colour for colour in found if colour != ground_rgb)
    # The variant is the figure's offset from the ground, so it survives any
    # rotation of the pair. It can never be 0 here: a figure that matched its
    # ground would have shown one colour and been read as void above.
    variant = (found[form_rgb] - ground) % 8

    # The cell shows exactly two colours, so a pixel that differs from the
    # ground is figure. The largest of its three channel differences is 0
    # exactly where it matches the ground, which keeps this exact while
    # running in C: a per-pixel Python loop was nearly all of decode's time.
    ground_block = Image.new("RGB", block.size, ground_rgb)
    r, g, b = ImageChops.difference(block, ground_block).split()
    mask = ImageChops.lighter(ImageChops.lighter(r, g), b).tobytes().translate(_NONZERO)
    match = render.TEMPLATES.get(mask)
    if match is None:
        raise LoadError(x, y, "no glyph matches this cell")
    form, scale = match

    if isa.lookup(form, variant) is None:
        raise LoadError(x, y, f"undefined instruction: {form.name} variant {variant}")
    return Cell(form, variant, scale, ground)


# Pillow reads the ceiling from a module global inside Image.open, so it
# cannot be passed per call and has to be set around the call instead. The
# lock stops two concurrent loads interleaving their save and restore, which
# would leave the host's limit at whatever the inner call set, permanently.
_LIMIT_LOCK = threading.Lock()


def _open_unguarded(path: str | os.PathLike[str]) -> Image.Image:
    """Open a plate image with Pillow's bomb check suspended.

    Vonal judges the size itself, just below. Deferring to Pillow's guard
    meant living with its two bands: over the ceiling it warns and hands the
    image over anyway, over twice it raises. Turning that first case into a
    refusal took warnings.catch_warnings, which mutates a second process-wide
    global and is no more thread-safe than this one. Checking here instead
    makes the refusal deterministic, ours, and able to say what the size was.

    The mutation covers only the header read, not the decode, and is held
    under the lock. It is still a window: another thread opening an unrelated
    image inside it sees no ceiling. Closing that would mean sniffing the
    format ourselves, which is a worse trade than a window this narrow.

    Keeping it narrow has one consequence worth naming. Image.crop consults
    the limit as well, so decode's per-cell crops are judged against whatever
    the host has set, not against MAX_PIXELS. A crop is one 64x64 cell, 4096
    pixels, so a host would have to have set the limit near zero for that to
    matter, and the alternative is holding this lock for the whole decode:
    twelve seconds on a large plate, rather than the header read.
    """
    with _LIMIT_LOCK:
        previous = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            return Image.open(path)
        finally:
            Image.MAX_IMAGE_PIXELS = previous


def load(path: str | os.PathLike[str]) -> Plate:
    """Open a plate image and decode it. The only way vonal opens a plate."""
    with _open_unguarded(path) as image:
        pixels = image.width * image.height
        if pixels > MAX_PIXELS:
            raise VonalError(
                f"{os.fspath(path)}: {pixels} pixels exceeds the ceiling of "
                f"{MAX_PIXELS}; a plate may be at most {MAX_CELLS} cells"
            )
        return decode(image)


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
