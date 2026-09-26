import io
from pathlib import Path

import pytest

from tools.layout import counted_loop, op, push
from vonal import isa, notation
from vonal.cell import Cell, Form, Plate
from vonal.isa import Op
from vonal.machine import Machine

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def blanked(plate):
    """The plate with every cell the loop owns replaced by a plain disc.

    That is all of row 0, row 1 from the column the loop turns north in, and
    the exit void. Grounds are kept, since the loop takes its colours from
    them, and so is everything else, like the cells under inversion's seed
    and ripple's table in row 2: those are composition, and the rebuild must
    leave them alone.
    """
    entry = next(x for x in range(plate.width) if plate.at(x, 1).form is Form.TRIANGLE_N)
    exit_x = next(x for x in range(plate.width) if plate.at(x, 2).is_void)
    owned = [(x, 0) for x in range(plate.width)]
    owned += [(x, 1) for x in range(entry, plate.width)]
    owned.append((exit_x, 2))
    rows = [list(row) for row in plate.cells]
    for x, y in owned:
        rows[y][x] = Cell(Form.DISC, 1, 0, rows[y][x].ground)
    return Plate(plate.width, plate.height, tuple(tuple(r) for r in rows))


def output(plate, stdin=""):
    out = io.StringIO()
    machine = Machine(plate, stdin=io.StringIO(stdin), stdout=out)
    machine.run(max_steps=100_000)
    assert machine.halted
    return out.getvalue()


def test_it_rebuilds_inversion_exactly():
    shipped = notation.parse((EXAMPLES / "inversion.vsr").read_text())
    body = [
        op(Op.DUP), *push(17), op(Op.MOD),
        op(Op.OVER), *push(17), op(Op.DIV), *push(3), op(Op.ADD),
        op(Op.OVER), op(Op.OVER), op(Op.GET),
        *push(7), op(Op.SWAP), op(Op.SUB),
        *push(3), op(Op.ROLL), op(Op.PUT),
    ]
    assert counted_loop(blanked(shipped), 17 * 17, body) == shipped


def test_it_rebuilds_ripple_exactly():
    shipped = notation.parse((EXAMPLES / "ripple.vsr").read_text())
    body = [
        op(Op.DUP), *push(19), op(Op.MOD),
        op(Op.OVER), *push(18), op(Op.MOD), *push(3), op(Op.ADD),
        op(Op.OVER), op(Op.OVER), op(Op.GET),
        *push(2), op(Op.GET),
        *push(3), op(Op.ROLL), op(Op.PUT),
    ]
    assert counted_loop(blanked(shipped), 7 * 19 * 18, body) == shipped


def test_the_body_sees_the_counter_running_down_to_zero():
    background = Plate(12, 3, tuple(tuple(Cell(Form.DISC, 1, 0, 7) for _ in range(12))
                                    for _ in range(3)))
    plate = counted_loop(background, 5, [op(Op.DUP), op(Op.OUT_NUM)])
    isa.validate(plate)
    assert output(plate) == "43210"


def test_a_short_body_still_exits_below_the_westward_row():
    # With nothing to do, the loop would end in row 0, where turning south
    # lands on row 1 and runs the loop again instead of halting.
    background = Plate(16, 3, tuple(tuple(Cell(Form.DISC, 1, 0, 2) for _ in range(16))
                                    for _ in range(3)))
    plate = counted_loop(background, 3, [])
    assert output(plate) == ""
    assert [x for x in range(16) if plate.at(x, 2).is_void] == [14]


@pytest.mark.parametrize("n,cells", [(0, "o1.."), (7, "o17."), (8, "o11.  o2.."),
                                     (289, "o14.  o24.  o21.")])
def test_push_spells_a_base_8_numeral(n, cells):
    tokens = ["".join((f.value, str(v), str(s) if s else ".", ".")) for f, v, s in push(n)]
    assert "  ".join(tokens) == cells


def test_a_body_may_not_turn():
    background = Plate(12, 3, tuple(tuple(Cell(Form.DISC, 1, 0, 0) for _ in range(12))
                                    for _ in range(3)))
    with pytest.raises(ValueError, match="layout owns the route"):
        counted_loop(background, 2, [(Form.TRIANGLE_N, 1, 0)])


def test_a_body_that_does_not_fit_is_refused():
    background = Plate(8, 3, tuple(tuple(Cell(Form.DISC, 1, 0, 0) for _ in range(8))
                                   for _ in range(3)))
    with pytest.raises(ValueError, match="needs 14 cells"):
        counted_loop(background, 2, [op(Op.DUP), op(Op.POP)] * 5)


def test_op_refuses_what_needs_an_immediate_or_a_heading():
    for operation in (Op.PUSH, Op.PUSH_ACC, Op.TURN, Op.HALT):
        with pytest.raises(ValueError):
            op(operation)


def plain(width, height, ground=7):
    return Plate(width, height, tuple(tuple(Cell(Form.DISC, 1, 0, ground) for _ in range(width))
                                      for _ in range(height)))


def test_setup_runs_once_and_leaves_its_values_beneath_the_counter():
    # The body prints what setup read, under the counter, on every pass.
    plate = counted_loop(plain(14, 3), 3, [op(Op.OVER), op(Op.OUT_NUM)], setup=[op(Op.IN_NUM)])
    assert output(plate, stdin="6\n") == "666"


@pytest.mark.parametrize("rows", [2, 4, 6])
def test_a_loop_winds_through_its_rows_and_exits_beneath_them(rows):
    # A body long enough to reach the last row, so every row of the route runs.
    body = [op(Op.DUP), op(Op.POP)] * (4 * rows)
    plate = counted_loop(plain(16, rows + 1), 4, [*body, op(Op.DUP), op(Op.OUT_NUM)], rows=rows)
    isa.validate(plate)
    assert output(plate) == "3210"
    assert sum(plate.at(x, rows).is_void for x in range(16)) == 1


@pytest.mark.parametrize("rows", [0, 1, 3])
def test_a_loop_needs_an_even_number_of_rows(rows):
    with pytest.raises(ValueError, match="even number of rows"):
        counted_loop(plain(16, 5), 2, [], rows=rows)
