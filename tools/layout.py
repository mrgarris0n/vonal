"""Lay out a counted loop across the top two rows of a plate.

inversion and ripple share one program shape, and both were placed by hand:

    row 0   seed  >  body ...................  v
    row 1         ^  ... body  exit  < < < <   <
    row 2                           void

The eye pushes the loop count, turns east into row 0, runs back west along
row 1 and north into row 0 again. Every pass decrements the counter, runs the
body, and tests a copy of the counter: at zero the exit turns south onto a
void and the plate halts. Cells the body does not need restate the heading
the eye already has, which costs a step and changes nothing.

Everything else on the plate is the caller's composition, and every cell the
loop writes keeps the ground it had there, so the program wears the picture's
colours.
"""

from __future__ import annotations

from collections.abc import Sequence

from vonal import isa
from vonal.cell import Cell, Form, Plate
from vonal.isa import Op

# One instruction: (form, variant, scale).
Instr = tuple[Form, int, int]

_ENCODING: dict[Op, tuple[Form, int]] = {}
for _form in Form:
    if _form is Form.VOID or _form.heading is not None:
        continue
    for _variant in range(1, 8):
        _found = isa.lookup(_form, _variant)
        if _found is not None:
            _ENCODING[_found] = (_form, _variant)


def op(operation: Op) -> Instr:
    """The cell for an operation that takes no immediate. Turns are the layout's."""
    if operation not in _ENCODING or operation in (Op.PUSH, Op.PUSH_ACC):
        raise ValueError(f"{operation.name} is not a plain body instruction")
    form, variant = _ENCODING[operation]
    return form, variant, 0


def push(n: int) -> list[Instr]:
    """Push n, one base-8 digit per cell: a push, then a push_acc per digit after it."""
    if n < 0:
        raise ValueError(f"push takes a non-negative literal, got {n}; negate it with NEG")
    digits = []
    while True:
        n, digit = divmod(n, 8)
        digits.append(digit)
        if not n:
            break
    first, *rest = reversed(digits)
    return [(Form.DISC, 1, first), *((Form.DISC, 2, digit) for digit in rest)]


def counted_loop(
    background: Plate,
    count: int,
    body: Sequence[Instr],
    *,
    setup: Sequence[Instr] = (),
    rows: int = 2,
) -> Plate:
    """background with a loop running `body` count times written over its top rows.

    `setup` runs once, before the count is pushed, and may leave values on the
    stack beneath it. The body starts each pass with the counter on top,
    running count - 1 down to 0, and must leave it there.

    The loop winds through the first `rows` rows, an even number: east along
    row 0, back and forth through the rows below, west along the last one and
    north up the column after the seed. The exit void goes in the row beneath.
    """
    if count < 1:
        raise ValueError(f"a loop runs at least once, got a count of {count}")
    if rows < 2 or rows % 2:
        raise ValueError(f"a loop winds through an even number of rows, got {rows}")
    if background.height <= rows:
        raise ValueError(f"a {rows}-row loop needs a row beneath it for its exit")
    for form, _, _ in (*setup, *body):
        if form is Form.VOID or form.heading is not None:
            raise ValueError("a body cell may not halt or turn; the layout owns the route")

    seed = [*setup, *push(count)]
    entry = len(seed)  # the column the loop turns north and east in
    width = background.width
    last = rows - 1

    # The route, as (x, y, heading) for every cell the loop body may occupy,
    # plus the turns that link the rows. The first and last rows reach the
    # return column's neighbour; the middle ones leave that column for the
    # turns between them.
    turns: list[tuple[int, int, Form]] = [(entry, 0, Form.TRIANGLE_E)]
    slots: list[tuple[int, int, Form]] = []
    for y in range(rows):
        if y % 2 == 0:
            start_x = entry + 1 if y == 0 else entry + 2
            if y:
                turns.append((entry + 1, y, Form.TRIANGLE_E))
            slots += [(x, y, Form.TRIANGLE_E) for x in range(start_x, width - 1)]
            turns.append((width - 1, y, Form.TRIANGLE_S))
        else:
            end_x = entry + 1 if y == last else entry + 2
            turns.append((width - 1, y, Form.TRIANGLE_W))
            slots += [(x, y, Form.TRIANGLE_W) for x in range(width - 2, end_x - 1, -1)]
            if y == last:
                turns.append((entry, y, Form.TRIANGLE_N))
            else:
                turns.append((entry + 1, y, Form.TRIANGLE_S))
    turns += [(entry, y, Form.TRIANGLE_N) for y in range(1, last)]  # the way back up

    cells = [*push(1), op(Op.SUB), *body, op(Op.DUP)]
    # The exit's void must sit beneath the loop, not inside it, so the exit
    # goes on the last row: a body that ends earlier runs round to it first.
    exit_at = max(len(cells), next(i for i, (_, y, _) in enumerate(slots) if y == last))
    if exit_at >= len(slots):
        raise ValueError(
            f"the loop needs {exit_at + 1} cells but {rows} rows of a "
            f"{width}-wide plate have {len(slots)}"
        )

    grid = [list(row) for row in background.cells]

    def put(x: int, y: int, form: Form, variant: int, scale: int) -> None:
        grid[y][x] = Cell(form, variant, scale, grid[y][x].ground)

    for x, instr in enumerate(seed):
        put(x, 0, *instr)
    for x, y, form in turns:
        put(x, y, form, 1, 0)
    for i, (x, y, heading) in enumerate(slots):
        if i < len(cells):
            put(x, y, *cells[i])
        elif i == exit_at:
            put(x, y, Form.TRIANGLE_S, 3, 0)
            put(x, rows, Form.VOID, 0, 0)
        else:
            put(x, y, heading, 1, 0)  # restates the heading the eye already has

    return Plate(background.width, background.height, tuple(tuple(r) for r in grid))
