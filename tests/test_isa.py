import pytest
from vonal.cell import Form
from vonal.isa import Op, lookup


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
