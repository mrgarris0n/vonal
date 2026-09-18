import threading
import time
import warnings

import pytest
from hypothesis import given, settings
from PIL import Image, UnidentifiedImageError

from vonal import decode as decode_module
from vonal import notation, palette, render
from vonal.cell import Cell, Form, Plate
from vonal.decode import decode
from vonal.errors import LoadError, VonalError
from tests.strategies import loadable_plates


def one(cell):
    return Plate(1, 1, ((cell,),))


def test_decodes_a_void_cell():
    plate = one(Cell(Form.VOID, ground=3))
    assert decode(render.render(plate)) == plate


def test_decodes_a_glyph_cell():
    plate = one(Cell(Form.RING, variant=1, scale=4, ground=0))
    assert decode(render.render(plate)) == plate


@given(loadable_plates())
@settings(max_examples=150, deadline=None)
def test_image_round_trip_is_identity(plate):
    assert decode(render.render(plate)) == plate


def test_dimensions_not_a_multiple_of_the_cell_size_are_rejected():
    with pytest.raises(LoadError, match="multiple of 64"):
        decode(Image.new("RGB", (100, 64), palette.rgb(0)))


def test_a_colour_outside_the_palette_is_rejected():
    with pytest.raises(LoadError, match="not in the palette"):
        decode(Image.new("RGB", (64, 64), (1, 2, 3)))


def test_more_than_two_colours_in_a_cell_is_rejected():
    image = render.render(one(Cell(Form.DISC, variant=5, scale=3, ground=0)))
    image.putpixel((1, 1), palette.rgb(4))
    with pytest.raises(LoadError, match="two colours"):
        decode(image)


def test_an_unrecognised_glyph_is_rejected():
    image = render.render(one(Cell(Form.DISC, variant=5, scale=3, ground=0)))
    for x in range(20, 44):  # scribble across the disc so it matches no template
        image.putpixel((x, 32), palette.rgb(0))
    with pytest.raises(LoadError, match="no glyph"):
        decode(image)


def test_an_undefined_form_variant_pair_is_rejected_at_load():
    # DISC variant 2 is undefined; it renders fine but must not load.
    image = render.render(one(Cell(Form.DISC, variant=2, scale=3, ground=0)))
    with pytest.raises(LoadError, match="undefined instruction"):
        decode(image)


def test_load_errors_name_the_cell():
    plate = Plate(2, 1, (
        (Cell(Form.VOID, ground=0), Cell(Form.DISC, variant=5, scale=3, ground=0)),
    ))
    image = render.render(plate)
    image.putpixel((64 + 1, 1), palette.rgb(4))
    with pytest.raises(LoadError) as excinfo:
        decode(image)
    assert (excinfo.value.x, excinfo.value.y) == (1, 0)


def test_a_plate_past_pillows_default_ceiling_is_allowed():
    # The regression this guard exists for: vonal compiled a 170x165 plate,
    # which is 115 megapixels, and loading it back warned over correct output.
    # Anything vonal can compile within its own cell ceiling must load clean.
    assert decode_module.MAX_PIXELS > Image.MAX_IMAGE_PIXELS
    assert decode_module.MAX_PIXELS >= 170 * 165 * render.CELL * render.CELL


def test_load_ignores_a_lower_ambient_pixel_limit(tmp_path, monkeypatch):
    # Proves the ceiling is actually applied at open time rather than merely
    # declared: at 5000 the 8192 pixel plate is a bomb as far as Pillow is
    # concerned, and load must still succeed silently.
    #
    # Not lower than that, deliberately. Only the header read runs with the
    # ceiling lifted, and Image.crop consults the limit too, so decode's
    # per-cell crops are still judged against whatever the host set. A crop is
    # one 64x64 cell, 4096 pixels, so that only bites below about 2048, where
    # a host has effectively disabled image loading anyway.
    plate = notation.parse("%plate 2x1\n\no.57  ....\n")
    png = tmp_path / "small.png"
    render.render(plate).save(png)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 5000)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert decode_module.load(png) == plate


def test_load_restores_the_ambient_pixel_limit(tmp_path, monkeypatch):
    # The ceiling is a Pillow module global. Raising it permanently would
    # relax the guard for every other image the host program opens, so the
    # previous value has to come back, including when decoding fails.
    render.render(notation.parse("%plate 2x1\n\no.57  ....\n")).save(tmp_path / "p.png")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 4242)

    decode_module.load(tmp_path / "p.png")
    assert Image.MAX_IMAGE_PIXELS == 4242

    bogus = tmp_path / "bogus.png"
    bogus.write_bytes(b"not a png")
    with pytest.raises(UnidentifiedImageError):
        decode_module.load(bogus)
    assert Image.MAX_IMAGE_PIXELS == 4242


def test_a_plate_over_the_ceiling_is_refused_not_merely_warned_about(
    tmp_path, monkeypatch
):
    # Pillow's own guard has two bands: over the ceiling it warns and hands
    # the image over anyway, over twice it raises. The first band is exactly
    # how a 115 megapixel plate came to run with a warning on stderr, so the
    # size is judged here rather than there, and the refusal has to be an
    # error in both. The ceiling is lowered rather than the image enlarged,
    # because a real one is 16384 pixels square.
    png = tmp_path / "over.png"
    render.render(notation.parse("%plate 2x1\n\no.57  ....\n")).save(png)
    with Image.open(png) as probe:
        assert probe.size == (128, 64)
    monkeypatch.setattr(decode_module, "MAX_PIXELS", 8000)   # under twice 8192

    with pytest.raises(VonalError, match="exceeds the ceiling") as caught:
        decode_module.load(png)
    assert "8192 pixels" in str(caught.value)
    assert "over.png" in str(caught.value)
    assert not isinstance(caught.value, Warning)


def test_concurrent_loads_leave_the_ambient_limit_intact(tmp_path, monkeypatch):
    # Pillow's ceiling is a process-wide global, so load has to set it and put
    # it back. Two loads interleaving that save and restore would have the
    # inner one save the outer one's temporary value and restore *that*,
    # leaving the host's limit wrong for good. Widen the window so the
    # interleaving is certain rather than lucky.
    png = tmp_path / "p.png"
    render.render(notation.parse("%plate 2x1\n\no.57  ....\n")).save(png)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 4242)

    opened = Image.open

    def slow_open(*args, **kwargs):
        time.sleep(0.02)
        return opened(*args, **kwargs)

    monkeypatch.setattr(Image, "open", slow_open)

    failures = []

    def worker():
        try:
            decode_module.load(png)
        except Exception as exc:          # noqa: BLE001 - reported, not swallowed
            failures.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert failures == []
    assert Image.MAX_IMAGE_PIXELS == 4242
