import io

import pytest

from vonal.errors import VonalRuntimeError
from vonal.machine import Machine
from vonal.notation import parse


def run(source, stdin=""):
    out = io.StringIO()
    machine = Machine(parse(source), stdin=io.StringIO(stdin), stdout=out)
    machine.run(max_steps=1000)
    return machine, out.getvalue()


def test_get_reads_the_field():
    # push x=1, push y=1, get -> the scale of cell (1,1), which is 6
    machine, _ = run(
        "%plate 4x2\n\no117  o117  @1.7  ....\n....  o167  ....  ....\n"
    )
    assert machine.stack == [6]


def test_put_writes_the_field():
    # push v=7, x=3, y=0, put -> field[0][3] becomes 7
    machine, _ = run("%plate 5x1\n\no177  o137  o107  @2.7  ....\n")
    assert machine.field[0][3] == 7


def test_put_leaves_the_plate_untouched():
    plate = parse("%plate 5x1\n\no177  o137  o107  @2.7  ....\n")
    machine = Machine(plate, stdin=io.StringIO(""), stdout=io.StringIO())
    machine.run(max_steps=100)
    assert plate.at(3, 0).scale == 0


def test_field_coordinates_wrap():
    # x = 1*8 + 1 = 9, and 9 % 7 == 2 on a 7-wide plate
    machine, _ = run("%plate 7x1\n\no177  o117  o217  o107  @2.7  ....  ....\n")
    assert machine.field[0][2] == 7


def test_put_into_a_void_cells_coordinates_is_valid_and_readable_back():
    # Controller ruling: `Cell`'s "void => scale 0" rule constrains the
    # rendered *plate*; `Machine.field` is a bare list[list[int]] with no
    # such constraint, and forbidding writes to a void cell's coordinates
    # would make most of a real plate unaddressable as a data surface. This
    # pins the ruled behaviour: (0,1) is void, yet a `put` targeting it
    # succeeds and a later `get` of the same coordinates returns the value.
    machine, _ = run(
        "%plate 8x2\n\n"
        "o157  o107  o117  @2.7  o107  o117  @1.7  ....\n"
        "....  ....  ....  ....  ....  ....  ....  ....\n"
    )
    assert machine.plate.at(0, 1).is_void
    assert machine.field[1][0] == 5
    assert machine.stack == [5]


@pytest.mark.parametrize("source", [
    # v = 1*8 + 1 = 9, which is outside 0-7 on the high side.
    "%plate 6x1\n\no117  o217  o107  o107  @2.7  ....\n",
    # push 1, negate -> -1, which is outside 0-7 on the low side.
    "%plate 6x1\n\no117  #6.7  o107  o107  @2.7  ....\n",
])
def test_put_of_an_out_of_range_value_is_an_error(source):
    with pytest.raises(VonalRuntimeError, match="0-7"):
        run(source)


def test_out_num_writes_decimal():
    _, out = run("%plate 3x1\n\no157  +1.7  ....\n")
    assert out == "5"


def test_out_char_writes_a_character():
    # 1 -> 1*8+0 = 8 -> 8*8+1 = 65 -> 'A'
    _, out = run("%plate 5x1\n\no117  o207  o217  +2.7  ....\n")
    assert out == "A"


def test_out_char_rejects_an_invalid_code_point():
    with pytest.raises(VonalRuntimeError, match="code point"):
        run("%plate 4x1\n\no117  #6.7  +2.7  ....\n")  # -1


def test_in_num_reads_an_integer():
    machine, _ = run("%plate 2x1\n\n+3.7  ....\n", stdin="42\n")
    assert machine.stack == [42]


def test_in_char_reads_one_code_point():
    machine, _ = run("%plate 2x1\n\n+4.7  ....\n", stdin="Az")
    assert machine.stack == [ord("A")]


@pytest.mark.parametrize("variant", [3, 4])
def test_eof_pushes_minus_one(variant):
    machine, _ = run(f"%plate 2x1\n\n+{variant}.7  ....\n", stdin="")
    assert machine.stack == [-1]


def test_malformed_numeric_input_is_an_error():
    with pytest.raises(VonalRuntimeError, match="not a number"):
        run("%plate 2x1\n\n+3.7  ....\n", stdin="banana\n")


@pytest.mark.parametrize(
    "text",
    ["1" + "0" * 5000, "-" + "9" * 4999 + "3", "12345" + "0" * 4321],
    ids=["power-of-ten", "negative", "leading-digits"],
)
def test_numbers_past_pythons_digit_limit_round_trip(text):
    # The stack is unbounded, but str() and int() refuse past about 4300
    # digits. Reading a number in and printing it back must still be exact.
    _, out = run("%plate 3x1\n\n+3.7  +1.7  ....\n", stdin=text + "\n")
    assert out == text


def test_a_number_past_the_digit_limit_is_computed_exactly():
    # 10**4400 built by mul, then printed: the crash this guards against.
    machine = Machine(parse("%plate 2x1\n\n+1.7  ....\n"), stdout=io.StringIO())
    machine.stack = [10**4400 - 1]
    machine.run()
    assert machine.stdout.getvalue() == "9" * 4400
