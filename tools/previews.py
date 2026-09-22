"""Thumbnails of every example plate, for the README's table.

Kept as files rather than generated on the fly because GitHub renders the
README from the repository, and shipped files can go stale: tests/test_docs.py
regenerates these in memory and compares.

    python tools/previews.py
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from PIL import Image

from vonal import decode

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
PREVIEWS = ROOT / "docs" / "previews"

# A box rather than a fixed width: the plates run from 30x4 to 58x96, so
# anything scaled on one axis alone is either a sliver or a column.
MAX_W, MAX_H = 200, 120


@contextmanager
def _ceiling() -> Iterator[None]:
    """Pillow's bomb threshold, raised to the one the language defines.

    The quine is 22 megapixels, past Pillow's default. Setting this at import
    would leave it raised for every image the importing process opens, which
    is a side effect a tool has no business having: it broke a decode test
    that asserts the two limits differ.
    """
    previous = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = decode.MAX_PIXELS
    try:
        yield
    finally:
        Image.MAX_IMAGE_PIXELS = previous


def thumbnail(png: Path) -> Image.Image:
    """The preview for one example image, fitted inside the box."""
    with _ceiling(), Image.open(png) as image:
        image.load()
        ratio = min(MAX_W / image.width, MAX_H / image.height)
        size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
        # LANCZOS, not NEAREST: at these reductions a cell is one or two
        # pixels, so point sampling drops whole glyphs and the texture with
        # them. The preview is meant to read as the plate's colour and weight.
        small = image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
        # Resampling eight flat colours produces thousands of intermediate
        # ones, which a PNG stores badly. Quantising back keeps the look and
        # roughly halves the file.
        return small.quantize(colors=64, dither=Image.Dither.NONE)


def sources() -> list[Path]:
    return sorted(EXAMPLES.glob("*.png"))


def main() -> None:
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    for png in sources():
        out = PREVIEWS / png.name
        thumbnail(png).save(out)
        print(f"{out.relative_to(ROOT)}  {thumbnail(png).size[0]}x{thumbnail(png).size[1]}")


if __name__ == "__main__":
    main()
