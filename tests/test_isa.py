import pytest
from vonal.cell import Cell, Form, Plate
from vonal.errors import LoadError
from vonal.isa import Op, lookup, validate


def test_void_halts_regardless_of_variant():
    for variant in range(8):
        assert lookup(Form.VOID, variant) is Op.HALT


@pytest.mark.parametrize("form,variant,op", [
    (Form.DISC, 0, Op.PUSH),
    (Form.DISC, 1, Op.PUSH_ACC),
    (Form.SQUARE, 0, Op.ADD),
    (Form.SQUARE, 5, Op.NEG),
    (Form.RHOMBUS, 4, Op.ROLL),
    (Form.TRIANGLE_N, 0, Op.TURN),
    (Form.TRIANGLE_S, 1, Op.TURN_IF),
    (Form.TRIANGLE_W, 2, Op.TURN_UNLESS),
    (Form.HALF_DISC, 2, Op.EQ),
    (Form.RING, 1, Op.PUT),
    (Form.CROSS, 3, Op.IN_CHAR),
])
def test_defined_pairs_resolve(form, variant, op):
    assert lookup(form, variant) is op


@pytest.mark.parametrize("form,variant", [
    (Form.DISC, 2), (Form.SQUARE, 6), (Form.RHOMBUS, 5),
    (Form.TRIANGLE_E, 3), (Form.HALF_DISC, 3), (Form.RING, 2), (Form.CROSS, 4),
])
def test_undefined_pairs_return_none(form, variant):
    assert lookup(form, variant) is None


def test_every_triangle_rotation_shares_the_same_variants():
    triangles = [Form.TRIANGLE_N, Form.TRIANGLE_E, Form.TRIANGLE_S, Form.TRIANGLE_W]
    for variant, op in ((0, Op.TURN), (1, Op.TURN_IF), (2, Op.TURN_UNLESS)):
        assert {lookup(t, variant) for t in triangles} == {op}


def test_validate_rejects_an_undefined_pair_anywhere_on_the_plate():
    # DISC variant 2 is undefined. It sits at (0,1), not (0,0), so this pins
    # that validate() walks the whole grid rather than stopping at the first
    # (defined) cell.
    plate = Plate(1, 2, (
        (Cell(Form.DISC, ground=1),),
        (Cell(Form.DISC, variant=2, ground=1),),
    ))
    with pytest.raises(LoadError, match="undefined instruction") as excinfo:
        validate(plate)
    assert (excinfo.value.x, excinfo.value.y) == (0, 1)


def test_validate_ignores_void_cells():
    plate = Plate(1, 1, ((Cell(Form.VOID, ground=1),),))
    validate(plate)  # must not raise


def test_validate_accepts_a_plate_of_only_defined_pairs():
    plate = Plate(1, 1, ((Cell(Form.DISC, variant=1, ground=0),),))
    validate(plate)  # must not raise


def test_len_op_is_twenty_six():
    # Stated in the spec: 11 forms, but HALT is shared by all void cells and
    # some forms have multiple variants -- the enum size is a fact worth
    # pinning so silent drift in the opcode set fails loudly.
    assert len(Op) == 26


def test_table_has_thirty_four_entries():
    # 34 of the 80 non-void (form, scale) pairs are defined instructions;
    # the rest are load errors. Stated in the spec (section 9).
    from vonal.isa import _TABLE
    assert len(_TABLE) == 34
