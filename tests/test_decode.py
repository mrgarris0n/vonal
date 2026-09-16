import pytest
from hypothesis import given, settings
from PIL import Image

from vonal import palette, render
from vonal.cell import Cell, Form, Plate
from vonal.decode import decode
from vonal.errors import LoadError
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
