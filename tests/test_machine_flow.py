import io
import pytest

from vonal.cell import Heading
from vonal.errors import VonalRuntimeError
from vonal.machine import Machine
from vonal.notation import parse


def run(source, max_steps=1000):
    machine = Machine(parse(source), stdin=io.StringIO(""), stdout=io.StringIO())
    machine.run(max_steps=max_steps)
    return machine


@pytest.mark.parametrize("variant,expected", [
    (0, [3, 4, 4]),      # dup
    (1, [3]),            # pop
    (2, [4, 3]),         # swap
    (3, [3, 4, 3]),      # over
])
def test_stack_operations(variant, expected):
    assert run(f"%plate 4x1\n\no.37  o.47  %{variant}.7  ....\n").stack == expected


def test_roll_moves_the_top_to_the_bottom_of_the_group():
    # push 1 2 3, push 3, roll  ->  3 1 2
    assert run("%plate 6x1\n\no.17  o.27  o.37  o.37  %4.7  ....\n").stack == [3, 1, 2]


@pytest.mark.parametrize("n", [4, 7])
def test_roll_deeper_than_the_stack_is_an_error(n):
    with pytest.raises(VonalRuntimeError, match="roll"):
        run(f"%plate 5x1\n\no.17  o.27  o.{n}7  %4.7  ....\n")


@pytest.mark.parametrize("variant,expected", [
    (0, [0]),   # gt: 3 > 4
    (1, [1]),   # lt: 3 < 4
    (2, [0]),   # eq: 3 == 4
])
def test_comparisons_push_one_or_zero(variant, expected):
    assert run(f"%plate 4x1\n\no.37  o.47  D{variant}.7  ....\n").stack == expected


def test_unconditional_turn_sets_the_heading_and_leaves_the_stack_alone():
    machine = run("%plate 2x2\n\no.77  v0.7\n....  ....\n")
    assert machine.halted
    assert machine.heading is Heading.S
    assert machine.stack == [7]


def test_turn_if_takes_the_branch_when_the_top_is_nonzero():
    machine = run("%plate 2x2\n\no.17  v1.7\n....  ....\n")
    assert machine.halted
    assert machine.heading is Heading.S
    assert machine.stack == []  # the guard was consumed


def test_turn_if_falls_through_when_the_top_is_zero():
    # Guard is 0, so the heading stays east and the eye wraps forever.
    machine = run("%plate 2x1\n\no.07  v1.7\n", max_steps=4)
    assert not machine.halted
    assert machine.heading is Heading.E


def test_turn_unless_is_the_mirror_of_turn_if():
    machine = run("%plate 2x2\n\no.07  v2.7\n....  ....\n")
    assert machine.halted
    assert machine.heading is Heading.S
    assert machine.stack == []


def test_a_west_triangle_turns_west():
    # Entry turns south into the west triangle, which sends the eye wrapping
    # west from x=0 to x=1, landing on a void.
    machine = run("%plate 2x2\n\nv0.7  ....\n<0.7  ....\n")
    assert machine.halted
    assert machine.heading is Heading.W
