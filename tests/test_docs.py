"""The README ships images and a table; both can drift from the examples."""

import io
import re
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from tools import previews

README = Path(__file__).resolve().parent.parent / "README.md"
ROW = re.compile(
    r'\| <img src="docs/previews/(?P<file>[\w-]+\.png)" width="(?P<w>\d+)" '
    r'height="(?P<h>\d+)" alt="(?P<alt>[\w-]+)"> \| `(?P<plate>[\w-]+)` \|'
)


def rows():
    return list(ROW.finditer(README.read_text()))


def test_the_table_lists_every_example_and_nothing_else():
    listed = {m["plate"] for m in rows()}
    shipped = {p.stem for p in previews.sources()}
    assert listed == shipped, f"table {sorted(listed)} vs examples {sorted(shipped)}"


@pytest.mark.parametrize("plate", sorted(p.stem for p in previews.sources()))
def test_each_preview_is_current(plate):
    # The failure this exists for: recolour or resize a plate, regenerate its
    # examples/*.png, and forget docs/previews. The README would then show the
    # old picture indefinitely, and nothing else in the suite opens these.
    shipped = previews.PREVIEWS / f"{plate}.png"
    assert shipped.exists(), f"run python tools/previews.py"

    fresh = previews.thumbnail(previews.EXAMPLES / f"{plate}.png").convert("RGB")
    with Image.open(shipped) as image:
        current = image.convert("RGB")

    assert current.size == fresh.size, f"{plate}: {current.size} shipped, {fresh.size} fresh"
    # Not byte equality: Pillow's resampling may shift by a step between
    # versions, and a red suite over one grey level would be noise. A stale
    # preview of a different plate is nowhere near this close.
    drift = max(ImageStat.Stat(ImageChops.difference(current, fresh)).mean)
    assert drift < 2.0, f"{plate}: mean channel drift {drift:.1f}, regenerate previews"


@pytest.mark.parametrize("plate", sorted(p.stem for p in previews.sources()))
def test_each_rows_declared_size_matches_the_file(plate):
    # The width and height attributes stop GitHub reflowing the table while
    # images load, so a wrong one is a visible defect rather than a nicety.
    match = next(m for m in rows() if m["plate"] == plate)
    with Image.open(previews.PREVIEWS / match["file"]) as image:
        assert image.size == (int(match["w"]), int(match["h"]))
    assert match["alt"] == plate
