"""The interpreter: an eye on a torus, an unbounded stack, and a bounded field."""

from __future__ import annotations

import re
import sys
from typing import TextIO

from vonal.cell import Cell, Heading, Plate
from vonal.errors import VonalRuntimeError
from vonal.isa import Op, lookup


class Machine:
    def __init__(self, plate: Plate, stdin: TextIO | None = None, stdout: TextIO | None = None):
        self.plate = plate
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout
        # The field is a mutable copy of the scale channel; the plate stays immutable.
        self.field: list[list[int]] = [[cell.scale for cell in row] for row in plate.cells]
        self.x = 0
        self.y = 0
        self.heading = Heading.E
        self.stack: list[int] = []
        self.halted = False
        self.steps = 0

    def _pop(self, x: int, y: int) -> int:
        if not self.stack:
            raise VonalRuntimeError(x, y, "stack underflow")
        return self.stack.pop()

    def _pop2(self, x: int, y: int) -> tuple[int, int]:
        # Top of stack is the *right* operand: for `a b SUB`, this returns
        # (a, b) so callers compute a - b, not b - a. The classic stack-
        # machine footgun -- get the pop order backwards and every
        # non-commutative op (SUB, DIV, MOD, GT, LT) silently flips.
        b = self._pop(x, y)
        a = self._pop(x, y)
        return a, b

    def step(self) -> bool:
        """Execute one cell. Returns False once the machine has halted."""
        if self.halted:
            return False
        x, y = self.x, self.y
        cell = self.plate.at(x, y)
        op = lookup(cell.form, cell.variant)
        if op is None:  # decode guarantees this cannot happen for a loaded plate
            raise VonalRuntimeError(
                x, y, f"undefined instruction: {cell.form.name} variant {cell.variant}"
            )
        self.steps += 1
        self._execute(op, cell, x, y)
        if not self.halted:
            dx, dy = self.heading.value
            self.x = (x + dx) % self.plate.width
            self.y = (y + dy) % self.plate.height
        return not self.halted

    def _execute(self, op: Op, cell: Cell, x: int, y: int) -> None:
        if op is Op.HALT:
            self.halted = True
        elif op is Op.PUSH:
            self.stack.append(self.field[y][x])
        elif op is Op.PUSH_ACC:
            self.stack.append(self._pop(x, y) * 8 + self.field[y][x])
        elif op in _ARITH:
            self._arith(op, x, y)
        elif op in _STACK:
            self._stack_op(op, x, y)
        elif op in _COMPARE:
            self._compare(op, x, y)
        elif op in _TURNS:
            self._turn(op, cell, x, y)
        elif op in _FIELD:
            self._field_op(op, x, y)
        else:
            self._io(op, x, y)

    def _stack_op(self, op: Op, x: int, y: int) -> None:
        if op is Op.DUP:
            value = self._pop(x, y)
            self.stack.extend((value, value))
        elif op is Op.POP:
            self._pop(x, y)
        elif op is Op.SWAP:
            a, b = self._pop2(x, y)
            self.stack.extend((b, a))
        elif op is Op.OVER:
            a, b = self._pop2(x, y)
            self.stack.extend((a, b, a))
        elif op is Op.ROLL:
            count = self._pop(x, y)
            if count < 0:
                raise VonalRuntimeError(x, y, f"roll of {count} is negative")
            if count > len(self.stack):
                raise VonalRuntimeError(x, y, f"roll of {count} exceeds the stack depth")
            if count > 1:
                group = self.stack[-count:]
                del self.stack[-count:]
                self.stack.extend([group[-1], *group[:-1]])

    def _compare(self, op: Op, x: int, y: int) -> None:
        a, b = self._pop2(x, y)
        self.stack.append(1 if {Op.GT: a > b, Op.LT: a < b, Op.EQ: a == b}[op] else 0)

    def _turn(self, op: Op, cell: Cell, x: int, y: int) -> None:
        if op is Op.TURN_IF and self._pop(x, y) == 0:
            return
        if op is Op.TURN_UNLESS and self._pop(x, y) != 0:
            return
        heading = cell.form.heading
        assert heading is not None, "isa maps the turns to triangles only"
        self.heading = heading

    def _arith(self, op: Op, x: int, y: int) -> None:
        if op is Op.NEG:
            self.stack.append(-self._pop(x, y))
            return
        a, b = self._pop2(x, y)
        if op is Op.ADD:
            self.stack.append(a + b)
        elif op is Op.SUB:
            self.stack.append(a - b)
        elif op is Op.MUL:
            self.stack.append(a * b)
        elif op is Op.DIV:
            if b == 0:
                raise VonalRuntimeError(x, y, "division by zero")
            self.stack.append(a // b)
        elif op is Op.MOD:
            if b == 0:
                raise VonalRuntimeError(x, y, "modulo by zero")
            self.stack.append(a % b)

    def _field_op(self, op: Op, x: int, y: int) -> None:
        fy = self._pop(x, y) % self.plate.height
        fx = self._pop(x, y) % self.plate.width
        if op is Op.GET:
            self.stack.append(self.field[fy][fx])
            return
        value = self._pop(x, y)
        if not 0 <= value <= 7:
            # Positions wrap; values never do.
            raise VonalRuntimeError(x, y, f"put value must be 0-7, got {value}")
        self.field[fy][fx] = value

    def _io(self, op: Op, x: int, y: int) -> None:
        if op is Op.OUT_NUM:
            self.stdout.write(_decimal(self._pop(x, y)))
        elif op is Op.OUT_CHAR:
            value = self._pop(x, y)
            try:
                self.stdout.write(chr(value))
            except (ValueError, OverflowError) as exc:
                raise VonalRuntimeError(x, y, f"{value} is not a valid code point") from exc
        elif op is Op.IN_CHAR:
            char = self.stdin.read(1)
            self.stack.append(-1 if char == "" else ord(char))
        elif op is Op.IN_NUM:
            line = self.stdin.readline()
            if line == "":
                self.stack.append(-1)
                return
            try:
                self.stack.append(_parse_decimal(line.strip()))
            except ValueError as exc:
                raise VonalRuntimeError(x, y, f"{line.strip()!r} is not a number") from exc

    def run(self, max_steps: int | None = None) -> None:
        """Run until halt, or until max_steps have been executed."""
        while not self.halted:
            if max_steps is not None and self.steps >= max_steps:
                return
            self.step()


_ARITH = {Op.ADD, Op.SUB, Op.MUL, Op.DIV, Op.MOD, Op.NEG}
_STACK = {Op.DUP, Op.POP, Op.SWAP, Op.OVER, Op.ROLL}
_COMPARE = {Op.GT, Op.LT, Op.EQ}
_TURNS = {Op.TURN, Op.TURN_IF, Op.TURN_UNLESS}
_FIELD = {Op.GET, Op.PUT}


# Python refuses to convert an int of more than about 4300 digits to or from
# text, but the stack is unbounded and `mul` gets there quickly. Converting in
# chunks keeps every individual str()/int() call under the limit without
# raising it, which would mean mutating process-wide interpreter state. 500
# is below the smallest limit a host can set (640).
_CHUNK = 500
_DIGITS = re.compile(r"[+-]?[0-9]+")


def _decimal(value: int) -> str:
    try:
        return str(value)
    except ValueError:
        pass
    sign, value = ("-" if value < 0 else ""), abs(value)
    chunks = []
    while value:
        value, low = divmod(value, 10**_CHUNK)
        chunks.append(low)
    head, *rest = reversed(chunks)
    return sign + str(head) + "".join(f"{chunk:0{_CHUNK}d}" for chunk in rest)


def _parse_decimal(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        # Only the digit limit is worth retrying; anything else is not a number.
        if not _DIGITS.fullmatch(text):
            raise
    body = text.lstrip("+-")
    value = 0
    for start in range(0, len(body), _CHUNK):
        chunk = body[start : start + _CHUNK]
        value = value * 10 ** len(chunk) + int(chunk)
    return -value if text.startswith("-") else value
