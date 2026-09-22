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
    (1, [3, 4, 4]),      # dup
    (2, [3]),            # pop
    (3, [4, 3]),         # swap
    (4, [3, 4, 3]),      # over
])
def test_stack_operations(variant, expected):
    assert run(f"%plate 4x1\n\no137  o147  %{variant}.7  ....\n").stack == expected


def test_roll_moves_the_top_to_the_bottom_of_the_group():
    # push 1 2 3, push 3, roll  ->  3 1 2
    assert run("%plate 6x1\n\no117  o127  o137  o137  %5.7  ....\n").stack == [3, 1, 2]


@pytest.mark.parametrize("n", [4, 7])
def test_roll_deeper_than_the_stack_is_an_error(n):
    with pytest.raises(VonalRuntimeError, match="exceeds the stack depth"):
        run(f"%plate 5x1\n\no117  o127  o1{n}7  %5.7  ....\n")


def test_negative_roll_is_an_error_with_a_message_that_names_the_fault():
    # A negative count does not "exceed the stack depth" -- that phrasing
    # (the message before this fix) misdescribes a different fault.
    with pytest.raises(VonalRuntimeError, match="negative"):
        run("%plate 6x1\n\no117  o127  o117  #6.7  %5.7  ....\n")


@pytest.mark.parametrize("variant,expected", [
    (1, [0]),   # gt: 3 > 4
    (2, [1]),   # lt: 3 < 4
    (3, [0]),   # eq: 3 == 4
])
def test_comparisons_push_one_or_zero(variant, expected):
    assert run(f"%plate 4x1\n\no137  o147  D{variant}.7  ....\n").stack == expected


def test_unconditional_turn_sets_the_heading_and_leaves_the_stack_alone():
    machine = run("%plate 2x2\n\no177  v1.7\n....  ....\n")
    assert machine.halted
    assert machine.heading is Heading.S
    assert machine.stack == [7]


def test_turn_if_takes_the_branch_when_the_top_is_nonzero():
    machine = run("%plate 2x2\n\no117  v2.7\n....  ....\n")
    assert machine.halted
    assert machine.heading is Heading.S
    assert machine.stack == []  # the guard was consumed


def test_turn_if_falls_through_when_the_top_is_zero():
    # Guard is 0, so the heading stays east and the eye wraps forever.
    machine = run("%plate 2x1\n\no107  v2.7\n", max_steps=4)
    assert not machine.halted
    assert machine.heading is Heading.E


def test_turn_unless_is_the_mirror_of_turn_if():
    machine = run("%plate 2x2\n\no107  v3.7\n....  ....\n")
    assert machine.halted
    assert machine.heading is Heading.S
    assert machine.stack == []


def test_a_west_triangle_turns_west():
    # Entry turns south into the west triangle, which sends the eye wrapping
    # west from x=0 to x=1, landing on a void.
    machine = run("%plate 2x2\n\nv1.7  ....\n<1.7  ....\n")
    assert machine.halted
    assert machine.heading is Heading.W
