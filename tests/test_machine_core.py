import io
import pytest

from vonal.cell import Heading
from vonal.errors import VonalRuntimeError
from vonal.machine import Machine
from vonal.notation import parse


def run(source, stdin="", max_steps=1000):
    machine = Machine(parse(source), stdin=io.StringIO(stdin), stdout=io.StringIO())
    machine.run(max_steps=max_steps)
    return machine


def test_starts_at_the_origin_heading_east():
    machine = Machine(parse("%plate 1x1\n\n....\n"))
    assert (machine.x, machine.y, machine.heading) == (0, 0, Heading.E)


def test_void_halts():
    machine = run("%plate 1x1\n\n....\n")
    assert machine.halted
    assert machine.steps == 1


def test_push_puts_the_immediate_on_the_stack():
    assert run("%plate 2x1\n\no.57  ....\n").stack == [5]


def test_push_acc_builds_a_base_eight_numeral():
    # 5, then 5*8 + 2 = 42
    assert run("%plate 3x1\n\no.57  o127  ....\n").stack == [42]


@pytest.mark.parametrize("variant,expected", [
    (0, [7]),    # 4 + 3
    (1, [1]),    # 4 - 3
    (2, [12]),   # 4 * 3
    (3, [1]),    # 4 // 3
    (4, [1]),    # 4 % 3
])
def test_arithmetic_pops_two_and_pushes_the_result(variant, expected):
    assert run(f"%plate 4x1\n\no.47  o.37  #{variant}.7  ....\n").stack == expected


def test_neg_negates_the_top():
    assert run("%plate 3x1\n\no.47  #5.7  ....\n").stack == [-4]


def test_division_uses_floored_semantics():
    # -7 // 2 is -4 in Python, not -3
    assert run("%plate 5x1\n\no.77  #5.7  o.27  #3.7  ....\n").stack == [-4]


def test_the_eye_wraps_east():
    # A one-row plate with no void: the eye must wrap and hit max_steps.
    machine = run("%plate 2x1\n\no.17  o.17\n", max_steps=5)
    assert not machine.halted
    assert machine.steps == 5


def test_stack_underflow_names_the_cell():
    with pytest.raises(VonalRuntimeError) as excinfo:
        run("%plate 2x1\n\n#0.7  ....\n")
    assert (excinfo.value.x, excinfo.value.y) == (0, 0)
    assert "stack underflow" in str(excinfo.value)


@pytest.mark.parametrize("variant", [3, 4])
def test_division_or_modulo_by_zero_is_an_error(variant):
    with pytest.raises(VonalRuntimeError, match="zero"):
        run(f"%plate 4x1\n\no.47  o.07  #{variant}.7  ....\n")


def test_the_field_starts_as_the_plate_scales_and_the_plate_is_untouched():
    plate = parse("%plate 2x1\n\no.57  ....\n")
    machine = Machine(plate, stdout=io.StringIO())
    assert machine.field == [[5, 0]]
    machine.field[0][0] = 1
    assert plate.at(0, 0).scale == 5
