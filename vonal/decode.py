"""PNG -> Plate, by exact template lookup. Nothing here is statistical."""

from __future__ import annotations

import os
import warnings
from contextlib import contextmanager

from PIL import Image

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

    # tobytes() predates every Pillow version this project has ever
    # targeted (unlike get_flattened_data(), added in 12.1, or the
    # deprecated getdata() it replaced), and byte-slice comparison against
    # the raw RGB triples is faster than either: no per-pixel tuple
    # construction and comparison, just a bytes slice compare.
    raw, form_bytes = block.tobytes(), bytes(form_rgb)
    mask = bytes(
        render.FORM if raw[i : i + 3] == form_bytes else render.GROUND
        for i in range(0, len(raw), 3)
    )
    match = render.TEMPLATES.get(mask)
    if match is None:
        raise LoadError(x, y, "no glyph matches this cell")
    form, scale = match

    if isa.lookup(form, variant) is None:
        raise LoadError(x, y, f"undefined instruction: {form.name} variant {variant}")
    return Cell(form, variant, scale, ground)


@contextmanager
def _bomb_guard():
    """Raise Pillow's pixel ceiling for the duration of one open.

    The limit is a module global that Pillow consults inside Image.open, so it
    has to be set around the call rather than passed to it, and put back after:
    importing vonal must not quietly relax the limit for every other image the
    host program happens to open. Past the ceiling Pillow only warns and
    carries on, which is how a 115 megapixel plate came to load and run with a
    warning on stderr, so the warning is promoted to an error here and turned
    into a VonalError by the caller.
    """
    previous = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            yield
    finally:
        Image.MAX_IMAGE_PIXELS = previous


def load(path: str | os.PathLike[str]) -> Plate:
    """Open a plate image and decode it. The only way vonal opens a plate."""
    try:
        with _bomb_guard(), Image.open(path) as image:
            return decode(image)
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise VonalError(
            f"{os.fspath(path)}: {exc} A plate may be at most {MAX_CELLS} cells."
        ) from exc


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
