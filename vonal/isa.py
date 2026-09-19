"""(form, variant) -> operation. Undefined pairs are errors, never no-ops."""

from __future__ import annotations

import enum

from vonal.cell import Form, Plate
from vonal.errors import LoadError


class Op(enum.Enum):
    HALT = enum.auto()
    PUSH = enum.auto()
    PUSH_ACC = enum.auto()
    ADD = enum.auto()
    SUB = enum.auto()
    MUL = enum.auto()
    DIV = enum.auto()
    MOD = enum.auto()
    NEG = enum.auto()
    DUP = enum.auto()
    POP = enum.auto()
    SWAP = enum.auto()
    OVER = enum.auto()
    ROLL = enum.auto()
    TURN = enum.auto()
    TURN_IF = enum.auto()
    TURN_UNLESS = enum.auto()
    GT = enum.auto()
    LT = enum.auto()
    EQ = enum.auto()
    GET = enum.auto()
    PUT = enum.auto()
    OUT_NUM = enum.auto()
    OUT_CHAR = enum.auto()
    IN_NUM = enum.auto()
    IN_CHAR = enum.auto()


_TRIANGLES = (Form.TRIANGLE_N, Form.TRIANGLE_E, Form.TRIANGLE_S, Form.TRIANGLE_W)

_TABLE: dict[tuple[Form, int], Op] = {
    (Form.DISC, 1): Op.PUSH,
    (Form.DISC, 2): Op.PUSH_ACC,
    (Form.SQUARE, 1): Op.ADD,
    (Form.SQUARE, 2): Op.SUB,
    (Form.SQUARE, 3): Op.MUL,
    (Form.SQUARE, 4): Op.DIV,
    (Form.SQUARE, 5): Op.MOD,
    (Form.SQUARE, 6): Op.NEG,
    (Form.RHOMBUS, 1): Op.DUP,
    (Form.RHOMBUS, 2): Op.POP,
    (Form.RHOMBUS, 3): Op.SWAP,
    (Form.RHOMBUS, 4): Op.OVER,
    (Form.RHOMBUS, 5): Op.ROLL,
    (Form.HALF_DISC, 1): Op.GT,
    (Form.HALF_DISC, 2): Op.LT,
    (Form.HALF_DISC, 3): Op.EQ,
    (Form.RING, 1): Op.GET,
    (Form.RING, 2): Op.PUT,
    (Form.CROSS, 1): Op.OUT_NUM,
    (Form.CROSS, 2): Op.OUT_CHAR,
    (Form.CROSS, 3): Op.IN_NUM,
    (Form.CROSS, 4): Op.IN_CHAR,
}

for _triangle in _TRIANGLES:
    _TABLE[(_triangle, 1)] = Op.TURN
    _TABLE[(_triangle, 2)] = Op.TURN_IF
    _TABLE[(_triangle, 3)] = Op.TURN_UNLESS


def lookup(form: Form, variant: int) -> Op | None:
    """The operation for a cell, or None if the pair is undefined."""
    if form is Form.VOID:
        return Op.HALT  # a void cell's variant is not representable, so it is ignored
    return _TABLE.get((form, variant))


def validate(plate: Plate) -> None:
    """Reject a plate that contains any undefined (form, variant) pair.

    decode() performs this check as part of loading a PNG, so a plate that
    started life as .vsr source and never goes through decode() -- because it
    compiles straight to PNG, or is fed to `run`/`trace` as text -- would
    otherwise be accepted even though the same program loaded from its own
    rendered image would be rejected. Text and image are two representations
    of one Plate (see cell.py), so they must accept the same program set;
    this walks every cell exactly as decode() implicitly does, up front,
    rather than only surfacing the fault if and when the eye happens to step
    on the offending cell.
    """
    for y, row in enumerate(plate.cells):
        for x, cell in enumerate(row):
            if not cell.is_void and lookup(cell.form, cell.variant) is None:
                raise LoadError(
                    x, y, f"undefined instruction: {cell.form.name} variant {cell.variant}"
                )
