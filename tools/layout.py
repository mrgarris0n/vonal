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


def counted_loop(background: Plate, count: int, body: Sequence[Instr]) -> Plate:
    """background with a loop running `body` count times written over its top rows.

    The body starts each pass with the counter on top of the stack, running
    count - 1 down to 0, and must leave it there. It is written into rows 0
    and 1 and the exit void into row 2, below wherever the loop ends.
    """
    if count < 1:
        raise ValueError(f"a loop runs at least once, got a count of {count}")
    if background.height < 3:
        raise ValueError("a loop needs two rows and a third for its exit")
    for form, _, _ in body:
        if form is Form.VOID or form.heading is not None:
            raise ValueError("a body cell may not halt or turn; the layout owns the route")

    seed = push(count)
    entry = len(seed)  # the column the loop turns north and east in
    width = background.width
    slots = [(x, 0) for x in range(entry + 1, width - 1)]
    slots += [(x, 1) for x in range(width - 2, entry, -1)]

    cells = [*push(1), op(Op.SUB), *body, op(Op.DUP)]
    # The exit needs the westward row beneath it for its void to sit in row 2,
    # so a body that ends in row 0 is padded round the corner first.
    cells += [(Form.TRIANGLE_E, 1, 0)] * max(0, (width - 2 - entry) - len(cells))
    cells.append((Form.TRIANGLE_S, 3, 0))
    if len(cells) > len(slots):
        raise ValueError(
            f"the loop needs {len(cells)} cells but a {width}-wide plate has {len(slots)}"
        )

    rows = [list(row) for row in background.cells]

    def put(x: int, y: int, form: Form, variant: int, scale: int) -> None:
        rows[y][x] = Cell(form, variant, scale, rows[y][x].ground)

    for x, instr in enumerate(seed):
        put(x, 0, *instr)
    put(entry, 0, Form.TRIANGLE_E, 1, 0)
    put(width - 1, 0, Form.TRIANGLE_S, 1, 0)
    put(width - 1, 1, Form.TRIANGLE_W, 1, 0)
    put(entry, 1, Form.TRIANGLE_N, 1, 0)
    for (x, y), instr in zip(slots, cells, strict=False):
        put(x, y, *instr)
    for x, y in slots[len(cells) :]:
        put(x, y, Form.TRIANGLE_E if y == 0 else Form.TRIANGLE_W, 1, 0)
    exit_x, _ = slots[len(cells) - 1]
    put(exit_x, 2, Form.VOID, 0, 0)

    return Plate(background.width, background.height, tuple(tuple(r) for r in rows))
