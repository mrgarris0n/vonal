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
        Cell(Form.VOID, variant=4)


def test_non_void_cell_rejects_variant_zero():
    # Variant 0 is the offset that would paint the figure in the ground's own
    # colour, so the cell would render as a void and decode back as one.
    Cell(Form.DISC, variant=3, ground=5)  # fine
    with pytest.raises(ValueError, match=r"variant 1\.\.7"):
        Cell(Form.DISC, variant=0, ground=5)


def test_a_figure_can_never_match_its_own_ground():
    # What used to be a rule the model enforced is now an identity: no legal
    # variant can produce a figure the same colour as the ground it sits on.
    for ground in range(8):
        for variant in range(1, 8):
            assert Cell(Form.DISC, variant, 0, ground).figure != ground


def test_rotating_figure_and_ground_together_keeps_the_instruction():
    # The property the relative encoding exists for: a plate can be recoloured
    # wholesale without changing a single opcode.
    base = Cell(Form.SQUARE, 4, 3, 0)
    for shift in range(8):
        rotated = Cell(base.form, base.variant, base.scale, (base.ground + shift) % 8)
        assert rotated.variant == base.variant
        assert rotated.figure == (base.figure + shift) % 8


@pytest.mark.parametrize("kwargs", [
    {"variant": 8}, {"variant": -1}, {"scale": 8}, {"ground": 8},
])
def test_channels_are_range_checked(kwargs):
    with pytest.raises(ValueError):
        Cell(Form.DISC, **{"ground": 1, **kwargs})


def test_plate_at_wraps_on_the_torus():
    a, b = Cell(Form.DISC, 1, ground=1), Cell(Form.SQUARE, 1, ground=1)
    plate = Plate(2, 1, ((a, b),))
    assert plate.at(0, 0) is a
    assert plate.at(2, 0) is a       # wrapped east
    assert plate.at(-1, 0) is b      # wrapped west
    assert plate.at(0, 5) is a       # wrapped south


def test_plate_replaced_returns_a_new_plate():
    a = Cell(Form.DISC, 1, ground=1)
    plate = Plate(1, 1, ((a,),))
    other = plate.replaced(0, 0, Cell(Form.VOID))
    assert plate.at(0, 0) is a
    assert other.at(0, 0).is_void


def test_plate_rejects_cells_that_do_not_match_its_shape():
    with pytest.raises(ValueError, match="width and height"):
        Plate(2, 1, ((Cell(Form.VOID),),))
