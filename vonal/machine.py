"""The interpreter: an eye on a torus, an unbounded stack, and a bounded field."""

from __future__ import annotations

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
        else:
            raise NotImplementedError(f"{op} is not implemented yet")

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

    def run(self, max_steps: int | None = None) -> None:
        """Run until halt, or until max_steps have been executed."""
        while not self.halted:
            if max_steps is not None and self.steps >= max_steps:
                return
            self.step()


_ARITH = {Op.ADD, Op.SUB, Op.MUL, Op.DIV, Op.MOD, Op.NEG}
