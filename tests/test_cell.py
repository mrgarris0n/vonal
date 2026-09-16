import pytest
from vonal.cell import Cell, Form, Heading, Plate


def test_form_glyphs_are_the_notation_characters():
    assert Form.VOID.value == "."
    assert Form.DISC.value == "o"
    assert Form.TRIANGLE_N.value == "^"
    assert len(Form) == 11


def test_only_triangles_carry_a_heading():
    assert Form.TRIANGLE_N.heading is Heading.N
    assert Form.TRIANGLE_W.heading is Heading.W
    assert Form.DISC.heading is None


def test_heading_deltas_use_image_axes():
    assert Heading.N.value == (0, -1)
    assert Heading.S.value == (0, 1)


def test_void_cell_must_have_zero_variant_and_scale():
    Cell(Form.VOID, ground=4)  # fine
    with pytest.raises(ValueError, match="void"):
        Cell(Form.VOID, scale=3)
    with pytest.raises(ValueError, match="void"):
        Cell(Form.VOID, variant=3)


def test_non_void_cell_rejects_form_colour_equal_to_ground():
    Cell(Form.DISC, variant=2, ground=5)  # fine
    with pytest.raises(ValueError, match="ground"):
        Cell(Form.DISC, variant=5, ground=5)


@pytest.mark.parametrize("kwargs", [
    {"variant": 8}, {"variant": -1}, {"scale": 8}, {"ground": 8},
])
def test_channels_are_range_checked(kwargs):
    with pytest.raises(ValueError):
        Cell(Form.DISC, **{"ground": 1, **kwargs})


def test_plate_at_wraps_on_the_torus():
    a, b = Cell(Form.DISC, ground=1), Cell(Form.SQUARE, ground=1)
    plate = Plate(2, 1, ((a, b),))
    assert plate.at(0, 0) is a
    assert plate.at(2, 0) is a       # wrapped east
    assert plate.at(-1, 0) is b      # wrapped west
    assert plate.at(0, 5) is a       # wrapped south


def test_plate_replaced_returns_a_new_plate():
    a = Cell(Form.DISC, ground=1)
    plate = Plate(1, 1, ((a,),))
    other = plate.replaced(0, 0, Cell(Form.VOID))
    assert plate.at(0, 0) is a
    assert other.at(0, 0).is_void


def test_plate_rejects_cells_that_do_not_match_its_shape():
    with pytest.raises(ValueError, match="width and height"):
        Plate(2, 1, ((Cell(Form.VOID),),))
